"""Protocol Bus consumer — reads messages from the Redis streams that the
protocol-bus-mcp server publishes.

The MCP ``/send`` endpoint resolves each message to one or more Redis stream
channels named ``protocol:{protocol}:{recipient}`` (or
``protocol:{protocol}:broadcast``) and appends the envelope with ``XADD``. By
default this consumer tails those streams with ``XREAD`` from a tracked last-id
to preserve the pre-EDCP runtime behavior. EDCP command lanes can opt into
durable Redis consumer groups, where this class creates the groups, reads with
``XREADGROUP``, and acknowledges handled entries with ``XACK``.

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
    from redis.exceptions import ResponseError as RedisResponseError
    from redis.exceptions import TimeoutError as RedisTimeoutError
except ModuleNotFoundError:

    class RedisTimeoutError(Exception):
        pass

    class RedisResponseError(Exception):
        pass

# Handler signature: async def handler(message: dict[str, Any]) -> None
Handler = Callable[[dict[str, Any]], Awaitable[None]]


class ProtocolBusConsumer:
    """Consumes messages from any subset of the six protocol lanes.

    For each protocol with a registered handler the consumer tails two channels:
    the agent-directed channel (``protocol:{proto}:{agent_id}``) and the
    broadcast channel (``protocol:{proto}:broadcast``). The default read model
    is legacy ``XREAD`` from ``$``. EDCP callers can enable consumer-group mode
    to read pending entries for the stable consumer first, then new entries.
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
        use_consumer_group: bool = False,
        consumer_group: str = "protocol-bus-orchestrator",
        consumer_name: str | None = None,
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
        self.use_consumer_group = use_consumer_group
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or agent_id
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
            "ProtocolBusConsumer starting for agent=%s lanes=%s group_mode=%s",
            self.agent_id,
            sorted(self.handlers),
            self.use_consumer_group,
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
        if self.use_consumer_group:
            await self._consume_lane_grouped(protocol, [agent_channel, broadcast_channel])
            return

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

    async def _consume_lane_grouped(self, protocol: str, channels: list[str]) -> None:
        handler = self.handlers[protocol]
        await self._ensure_consumer_groups(channels)
        pending_streams = {channel: "0" for channel in channels}
        new_streams = {channel: ">" for channel in channels}
        while self._running:
            try:
                records = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams=pending_streams,
                    count=self.count,
                    block=1,
                )
                if not records:
                    records = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.consumer_name,
                        streams=new_streams,
                        count=self.count,
                        block=self.block_ms,
                    )
            except asyncio.CancelledError:
                raise
            except RedisTimeoutError as exc:
                LOGGER.debug(
                    "ProtocolBusConsumer xreadgroup timed out while idle on lane %s: %s",
                    protocol,
                    exc,
                )
                continue
            except Exception as exc:
                LOGGER.warning(
                    "ProtocolBusConsumer xreadgroup failed on lane %s: %s", protocol, exc
                )
                await asyncio.sleep(1.0)
                continue

            if not records:
                continue

            for channel, entries in records:
                for entry_id, fields in entries:
                    handled = await self._dispatch(protocol, handler, channel, entry_id, fields)
                    if handled:
                        await self._ack_entry(protocol, channel, entry_id)

    async def _ensure_consumer_groups(self, channels: list[str]) -> None:
        for channel in channels:
            try:
                await self.redis.xgroup_create(
                    name=channel,
                    groupname=self.consumer_group,
                    id="0-0",
                    mkstream=True,
                )
            except RedisResponseError as exc:
                if "BUSYGROUP" in str(exc).upper():
                    continue
                raise

    async def _ack_entry(self, protocol: str, channel: str, entry_id: str) -> None:
        try:
            await self.redis.xack(channel, self.consumer_group, entry_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning(
                "ProtocolBusConsumer xack failed on lane %s channel=%s entry=%s: %s",
                protocol,
                channel,
                entry_id,
                exc,
            )

    async def _dispatch(
        self,
        protocol: str,
        handler: Handler,
        channel: str,
        entry_id: str,
        fields: dict[str, Any],
    ) -> bool:
        message = self._decode_entry(channel, entry_id, fields)
        if message is None:
            return True
        envelope_protocol = str(message.get("envelope", {}).get("protocol", ""))
        if envelope_protocol != protocol:
            LOGGER.warning(
                "ProtocolBusConsumer dropping entry %s from lane %s with envelope protocol %r",
                entry_id,
                protocol,
                envelope_protocol,
            )
            return True
        try:
            await handler(message)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception(
                "ProtocolBusConsumer handler for lane %s failed on entry %s",
                protocol,
                entry_id,
            )
            return False

    @staticmethod
    def _decode_entry(
        channel: str, entry_id: str, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        normalized: dict[str, Any] = {}
        for key, value in (fields or {}).items():
            text_key = key.decode("utf-8", errors="replace") if isinstance(key, bytes) else str(key)
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            normalized[text_key] = value
        fields = normalized
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
