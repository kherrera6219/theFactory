"""Operations router: alerts, agents, metrics summary, events, logicnodes, and projects."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel


class AlertStateUpdate(BaseModel):
    state: str


def build_operations_router() -> APIRouter:
    from api_gateway import main as gateway_main

    router = APIRouter(tags=["operations"])

    @router.get("/v1/operations/summary")
    async def get_operations_summary(
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal("/internal/operations/summary")

    @router.get("/v1/operations/agents")
    async def get_operations_agents(
        mission_limit: int = Query(default=1000, ge=50, le=5000),
        assignment_limit: int = Query(default=1000, ge=50, le=5000),
        event_limit: int = Query(default=300, ge=50, le=2000),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(
            "/internal/operations/agents",
            params={
                "mission_limit": mission_limit,
                "assignment_limit": assignment_limit,
                "event_limit": event_limit,
            },
        )

    @router.get("/v1/operations/events")
    async def get_operations_events(
        limit: int = Query(default=200, ge=1, le=1000),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal("/internal/operations/events", params={"limit": limit})

    @router.get("/v1/operations/agent-events")
    async def get_operations_agent_events(
        limit: int = Query(default=200, ge=1, le=1000),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal("/internal/operations/agent-events", params={"limit": limit})

    @router.get("/v1/operations/agent-integrations")
    async def get_operations_agent_integrations(
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal("/internal/operations/agent-integrations")

    @router.get("/v1/operations/logicnodes")
    async def get_operations_logicnodes(
        limit: int = Query(default=200, ge=1, le=1000),
        mission_id: str | None = Query(default=None),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        params: dict[str, Any] = {"limit": limit}
        if mission_id:
            params["mission_id"] = mission_id
        return await gateway_main._proxy_get_internal("/internal/operations/logicnodes", params=params)

    @router.get("/v1/operations/pod-assignments")
    async def get_operations_pod_assignments(
        limit: int = Query(default=200, ge=1, le=1000),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(
            "/internal/operations/pod-assignments",
            params={"limit": limit},
        )

    @router.get("/v1/operations/projects")
    async def get_operations_projects(
        limit: int = Query(default=100, ge=1, le=500),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal("/internal/operations/projects", params={"limit": limit})

    @router.get("/v1/operations/projects/{project_id}/audit-events")
    async def get_project_audit_events(
        project_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
        mission_id: str | None = Query(default=None),
        agent_id: str | None = Query(default=None),
        tool_name: str | None = Query(default=None),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        params: dict[str, Any] = {"limit": limit}
        if mission_id:
            params["mission_id"] = mission_id
        if agent_id:
            params["agent_id"] = agent_id
        if tool_name:
            params["tool_name"] = tool_name
        return await gateway_main._proxy_get_internal(
            f"/internal/operations/projects/{project_id}/audit-events",
            params=params,
        )

    @router.get("/v1/operations/alerts")
    async def get_operations_alerts(
        limit: int = Query(default=50, ge=1, le=200),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal("/internal/operations/alerts", params={"limit": limit})

    @router.post("/v1/operations/alerts/{alert_id}/state")
    async def update_operations_alert_state(
        alert_id: str,
        payload: AlertStateUpdate,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_post_internal(
            f"/internal/operations/alerts/{alert_id}/state",
            json_body=payload.model_dump(),
        )

    return router
