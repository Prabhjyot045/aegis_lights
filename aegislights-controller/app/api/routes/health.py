"""
Copilot instructions:

Implement a basic healthcheck endpoint for the controller service.

Requirements:
- Use APIRouter from fastapi.
- Expose a GET endpoint `/health` that returns:
  { "status": "ok" }

- This route should not depend on any heavy components.
"""


from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
	"""Simple health endpoint for liveness probing."""

	return {"status": "ok"}
