"""Protocol Bus consumer — reads messages from the Redis streams that the
protocol-bus-mcp server publishes.

The MCP ``/send`` endpoint resolves each message to one or more Redis stream
channels named ``protocol:{protocol}:{recipient}`` (or
``protocol:{protocol}:broadcast``) and appends the envelope with ``XADD``. This
consumer tails those streams with ``XREAD`` (the bus does not create consumer
groups, so plain ``XREAD`` from a tracked last-id is the matching read model)
and dispatches each decoded message to a per-protocol async handler.

Every message handed to a handler is a ``dict`` with the keys the bus writes
into each stream entry:

    {
        "envelope":   <decoded MessageEnvelope dict>,
        "payload":    <decoded protocol payload dict>,
        "sender":     <sender agent id str>,
        "channel":    <the redis channel it arrived on>,
        "entry_id":   <the redis stream id>,
    }

Handlers must be ``async`` and accept that single dict. A handler raising is
logged and swallowed — one bad message must never tear down the lane loop.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

LOGGER = logging.getLogger(__name__)

try:
    from redis.exceptions import TimeoutError as RedisTimeoutError
except ModuleNotFoundError:

    class RedisTimeoutError(Exception):
        pass

# Handler signature: async def handler(message: dict[str, Any]) -> None
Handler = Callable[[dict[str, Any]], Awaitable[None]]


class ProtocolBusConsumer:
    """Consumes messages from any subset of the six protocol lanes.

    For each protocol with a registered handler the consumer tails two channels:
    the agent-directed channel (``protocol:{proto}:{agent_id}``) and the
    broadcast channel (``protocol:{proto}:broadcast``). New entries are read with
    ``XREAD`` starting at ``$`` (only messages published after start), so the
    consumer never reprocesses history on restart.
    """

    PROTOCOLS = ["alpha", "beta", "delta", "sigma", "omega", "rho"]

    def __init__(
        self,
        redis_client: Any,
        agent_id: str,
        handlers: dict[str, Handler],
        *,
        block_ms: int = 5000,
        count: int = 20,
    ) -> None:
        """handlers: {protocol_name: async callable(message) -> None}."""
        self.redis = redis_client
        self.agent_id = agent_id
        self.handlers = {
            proto: handler
            for proto, handler in handlers.items()
            if proto in self.PROTOCOLS
        }
        self.block_ms = block_ms
        self.count = count
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def stop(self) -> None:
        self._running = False

    async def start(self) -> None:
        if self.redis is None or not self.handlers:
            LOGGER.info(
                "ProtocolBusConsumer not started (redis=%s handlers=%d)",
                self.redis is not None,
                len(self.handlers),
            )
            return
        self._running = True
        LOGGER.info(
            "ProtocolBusConsumer starting for agent=%s lanes=%s",
            self.agent_id,
            sorted(self.handlers),
        )
        try:
            await asyncio.gather(
                *(self._consume_lane(proto) for proto in self.handlers)
            )
        finally:
            self._running = False

    async def _consume_lane(self, protocol: str) -> None:
        agent_channel = f"protocol:{protocol}:{self.agent_id}"
        broadcast_channel = f"protocol:{protocol}:broadcast"
        # "$" means "only entries added after we begin reading". We then advance
        # the per-channel cursor to the last id we saw on each iteration.
        cursors: dict[str, str] = {agent_channel: "$", broadcast_channel: "$"}
        handler = self.handlers[protocol]

        while self._running:
            try:
                streams = await self.redis.xread(
                    cursors,
                    count=self.count,
                    block=self.block_ms,
                )
            except asyncio.CancelledError:
                raise
            except RedisTimeoutError as exc:
                LOGGER.debug(
                    "ProtocolBusConsumer xread timed out while idle on lane %s: %s",
                    protocol,
                    exc,
                )
                continue
            except Exception as exc:
                LOGGER.warning(
                    "ProtocolBusConsumer xread failed on lane %s: %s", protocol, exc
                )
                # Back off briefly so a persistent Redis error does not hot-loop.
                await asyncio.sleep(1.0)
                continue

            if not streams:
                continue

            for channel, entries in streams:
                for entry_id, fields in entries:
                    cursors[channel] = entry_id
                    await self._dispatch(protocol, handler, channel, entry_id, fields)

    async def _dispatch(
        self,
        protocol: str,
        handler: Handler,
        channel: str,
        entry_id: str,
        fields: dict[str, Any],
    ) -> None:
        message = self._decode_entry(channel, entry_id, fields)
        if message is None:
            return
        try:
            await handler(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception(
                "ProtocolBusConsumer handler for lane %s failed on entry %s",
                protocol,
                entry_id,
            )

    @staticmethod
    def _decode_entry(
        channel: str, entry_id: str, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        envelope_raw = fields.get("envelope")
        payload_raw = fields.get("payload")
        envelope: dict[str, Any] = {}
        payload: dict[str, Any] = {}
        if isinstance(envelope_raw, str) and envelope_raw:
            try:
                envelope = json.loads(envelope_raw)
            except json.JSONDecodeError as exc:
                LOGGER.warning(
                    "ProtocolBusConsumer dropping entry %s with invalid envelope: %s",
                    entry_id,
                    exc,
                )
                return None
        if isinstance(payload_raw, str) and payload_raw:
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                payload = {}
        return {
            "envelope": envelope,
            "payload": payload,
            "sender": fields.get("sender", ""),
            "channel": channel,
            "entry_id": entry_id,
        }
