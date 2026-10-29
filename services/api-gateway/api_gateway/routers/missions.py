"""Missions query, evidence, and artifact proxy router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query


def build_missions_router() -> APIRouter:
    from api_gateway import main as gateway_main

    router = APIRouter(tags=["missions"])

    @router.get("/v1/missions/{mission_id}")
    async def get_mission(
        mission_id: str,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}")

    @router.get("/v1/missions")
    async def list_missions(
        limit: int = Query(default=20, ge=1, le=200),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal("/missions", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/events")
    async def get_mission_events(
        mission_id: str,
        limit: int = Query(default=50, ge=1, le=500),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/events", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/pod-assignment")
    async def get_mission_pod_assignment(
        mission_id: str,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/internal/missions/{mission_id}/pod-assignment")

    @router.get("/v1/missions/{mission_id}/chain-trace")
    async def get_mission_chain_trace(
        mission_id: str,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/internal/missions/{mission_id}/chain-trace")

    @router.post("/v1/sows", status_code=201)
    async def create_sow(
        payload: dict[str, Any],
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_post_internal("/internal/sows", json_body=payload, timeout=15.0)

    @router.get("/v1/sows/{sow_id}")
    async def get_sow(
        sow_id: str,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/internal/sows/{sow_id}")

    @router.post("/v1/pm/feature-contract")
    async def create_pm_feature_contract(
        payload: dict[str, Any],
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        prompt = str(payload.get("prompt") or payload.get("request") or "").strip()
        if len(prompt) < 3:
            raise HTTPException(status_code=400, detail="prompt must be at least 3 characters")
        body_to_forward = {
            **payload,
            "prompt": prompt,
        }
        return await gateway_main._proxy_post_internal(
            "/internal/pm/feature-contract",
            json_body=body_to_forward,
            timeout=120.0,
        )

    @router.get("/v1/missions/{mission_id}/logicnodes")
    async def get_mission_logicnodes(
        mission_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/logicnodes", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/knowledge")
    async def get_mission_knowledge(
        mission_id: str,
        limit: int = Query(default=100, ge=1, le=500),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/knowledge", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/knowledge-graph")
    async def get_mission_knowledge_graph(
        mission_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/knowledge-graph", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/audit-reports")
    async def get_mission_audit_reports(
        mission_id: str,
        limit: int = Query(default=50, ge=1, le=200),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/audit-reports", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/audit-artifacts")
    async def get_mission_audit_artifacts(
        mission_id: str,
        limit: int = Query(default=50, ge=1, le=200),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/audit-artifacts", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/audit-events")
    async def get_mission_audit_events(
        mission_id: str,
        limit: int = Query(default=100, ge=1, le=500),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/audit-events", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/build-artifacts")
    async def get_mission_build_artifacts(
        mission_id: str,
        limit: int = Query(default=50, ge=1, le=200),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[dict[str, Any]]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/build-artifacts", params={"limit": limit})

    @router.get("/v1/missions/{mission_id}/build-artifacts/{artifact_id}")
    async def get_mission_build_artifact(
        mission_id: str,
        artifact_id: str,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/build-artifacts/{artifact_id}")

    @router.get("/v1/missions/{mission_id}/artifact")
    async def download_mission_artifact(
        mission_id: str,
        artifact_id: str | None = Query(default=None),
        artifact_type: str | None = Query(default=None),
        format: str = Query(default="json"),
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> Any:
        gateway_main._require_reader_access(x_api_key=x_api_key, authorization=authorization)
        params: dict[str, Any] = {"format": format}
        if artifact_id:
            params["artifact_id"] = artifact_id
        if artifact_type:
            params["artifact_type"] = artifact_type
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/artifact", params=params)

    @router.get("/v1/missions/{mission_id}/token-usage")
    async def get_mission_token_usage(
        mission_id: str,
        x_api_key: str | None = Header(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        gateway_main._require_operator_access(x_api_key=x_api_key, authorization=authorization)
        return await gateway_main._proxy_get_internal(f"/missions/{mission_id}/token-usage")

    return router
