from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
	"""Simple health endpoint for liveness probing."""

	return {"status": "ok"}
