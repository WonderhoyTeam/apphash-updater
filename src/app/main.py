import asyncio
import logging
from contextlib import asynccontextmanager

import UnityPy
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings
from .constants import ALL_REGIONS
from .updater import get_cache, scheduler_loop, update_all, update_region

logger = logging.getLogger("wonderhoy")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _check_admin_key(api_key: str | None = Security(api_key_header)):
    if not settings.admin_api_key:
        raise HTTPException(503, "Admin API key not configured")
    if api_key != settings.admin_api_key:
        raise HTTPException(401, "Invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    UnityPy.config.FALLBACK_VERSION_WARNED = True
    UnityPy.config.FALLBACK_UNITY_VERSION = settings.unity_version
    task = asyncio.create_task(scheduler_loop())
    logger.info("Scheduler started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Wonderhoy AppHash API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def get_all_regions():
    cache = get_cache()
    return {r: cache.get(r) for r in settings.region_list}


@app.get("/{region}")
async def get_region(region: str):
    region = region.upper()
    if region not in ALL_REGIONS:
        raise HTTPException(404, f"Unknown region: {region}")
    if region not in settings.region_list:
        raise HTTPException(404, f"Region {region} is not enabled")
    data = get_cache().get(region)
    if not data:
        raise HTTPException(404, f"No data for {region} yet")
    return data


@app.post("/admin/refresh")
async def admin_refresh(
    region: str | None = None,
    _: None = Security(_check_admin_key),
):
    if region:
        region = region.upper()
        if region not in settings.region_list:
            raise HTTPException(404, f"Region {region} not enabled")
        result = await update_region(region, force=True)
        return {"region": region, "status": "ok" if result else "failed"}
    results = await update_all(force=True)
    return {"status": results}


def cli():
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
