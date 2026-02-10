import asyncio
import logging
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone

import aiohttp
import UnityPy
import UnityPy.enums
import UnityPy.enums.ClassIDType
from bs4 import BeautifulSoup

from .config import settings
from .constants import (
    APKPURE_URL_TEMPLATE,
    CN_APK_URL,
    PACKAGE_NAME_MAP,
    QOOAPP_APP_ID_MAP,
    QOOAPP_URL_TEMPLATE,
    TAPTAP_APP_ID_MAP,
    TAPTAP_CN_URL_TEMPLATE,
    USER_AGENT,
)
from .generated.sekai import AndroidPlayerSettingConfig
from .generated.uttcgen import UTTCGen_AsInstance
from .helpers import compare_version, enum_candidates, enum_package

logger = logging.getLogger("wonderhoy.updater")

# In-memory cache: region -> {appVersion, appHash, multiPlayVersion, dataVersion, assetHash, updatedAt}
_cache: dict[str, dict] = {}
_lock = asyncio.Lock()


def get_cache() -> dict[str, dict]:
    return _cache


async def get_app_ver_from_qooapp(app_id: str) -> str:
    url = QOOAPP_URL_TEMPLATE.format(app_id=app_id)
    async with aiohttp.ClientSession() as session:
        async with session.get(url, proxy=settings.http_proxy) as resp:
            if resp.status != 200:
                raise RuntimeError(f"QooApp returned {resp.status} for app {app_id}")
            data = await resp.text()
            soup = BeautifulSoup(data, "html.parser")
            app_info_tree = soup.select("ul.app-info.android")[0]
            return app_info_tree.find_all(class_="row")[1].var.text


async def get_app_ver_from_taptap_cn(app_id: str) -> str:
    url = TAPTAP_CN_URL_TEMPLATE.format(app_id=app_id)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, headers={"User-Agent": USER_AGENT}, proxy=settings.http_proxy
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"TapTap CN returned {resp.status} for app {app_id}")
            data = await resp.text()
            match = re.search(r'"softwareVersion":"(\d+\.\d+\.\d+)"', data)
            if not match:
                raise RuntimeError(f"Could not parse version from TapTap CN for app {app_id}")
            return match.group(1)


async def download_apk(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, proxy=settings.http_proxy) as resp:
            if resp.status != 200:
                raise RuntimeError(f"APK download failed: {resp.status} from {url}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".apk") as tmp:
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    tmp.write(chunk)
                logger.info(f"APK downloaded to {tmp.name}")
                return tmp.name


def extract_app_hash(apk_path: str, expected_app_ver: str) -> dict | None:
    env = UnityPy.Environment()
    with zipfile.ZipFile(apk_path, "r") as zip_ref:
        candidates = [
            candidate
            for package in enum_package(zip_ref)
            for candidate in enum_candidates(
                package,
                lambda fn: fn.split("/")[-1]
                in {
                    "6350e2ec327334c8a9b7f494f344a761",
                    "c726e51b6fe37463685916a1687158dd",
                    "data.unity3d",
                },
            )
        ]
        for _candidate, stream, _ in candidates:
            env.load_file(stream)

    for reader in env.objects:
        if reader.type == UnityPy.enums.ClassIDType.MonoBehaviour:
            if reader.peek_name() == "production_android":
                config = UTTCGen_AsInstance(AndroidPlayerSettingConfig, reader)
                app_version = f"{config.clientMajorVersion}.{config.clientMinorVersion}.{config.clientBuildVersion}"
                assert compare_version(app_version, expected_app_ver), (
                    f"Version mismatch: {app_version} != {expected_app_ver}"
                )
                data_version = (
                    f"{config.clientDataMajorVersion}.{config.clientDataMinorVersion}.{config.clientDataBuildVersion}"
                )
                ab_version = (
                    f"{config.clientMajorVersion}.{config.clientMinorVersion}.{config.clientDataRevision}"
                )
                return {
                    "appVersion": app_version,
                    "appHash": config.clientAppHash,
                    "assetHash": config.assetHash,
                    "dataVersion": data_version,
                    "multiPlayVersion": ab_version,
                }
    return None


async def _get_latest_version(region: str) -> str:
    if region in QOOAPP_APP_ID_MAP:
        return await get_app_ver_from_qooapp(QOOAPP_APP_ID_MAP[region])
    if region in TAPTAP_APP_ID_MAP:
        return await get_app_ver_from_taptap_cn(TAPTAP_APP_ID_MAP[region])
    raise ValueError(f"Unknown region: {region}")


def _get_apk_url(region: str) -> str:
    if region == "CN":
        return CN_APK_URL
    return APKPURE_URL_TEMPLATE.format(packageName=PACKAGE_NAME_MAP[region])


async def update_region(region: str, *, force: bool = False) -> dict | None:
    async with _lock:
        cached = _cache.get(region)

    latest_ver = await _get_latest_version(region)
    if not force and cached and cached.get("appVersion") == latest_ver:
        logger.info(f"[{region}] version {latest_ver} unchanged, skipping")
        return cached

    logger.info(f"[{region}] new version {latest_ver}, downloading APK...")
    apk_path = await download_apk(_get_apk_url(region))
    try:
        result = extract_app_hash(apk_path, latest_ver)
        if not result:
            logger.error(f"[{region}] failed to extract app hash")
            return None
        result["updatedAt"] = datetime.now(timezone.utc).isoformat()
        async with _lock:
            _cache[region] = result
        logger.info(f"[{region}] updated: v{latest_ver} hash={result['appHash']}")
        return result
    finally:
        try:
            os.unlink(apk_path)
        except OSError:
            pass


async def update_all(*, force: bool = False) -> dict[str, str]:
    results = {}
    for region in settings.region_list:
        try:
            r = await update_region(region, force=force)
            results[region] = "ok" if r else "failed"
        except Exception:
            logger.exception(f"[{region}] update failed")
            results[region] = "error"
    return results


async def scheduler_loop():
    interval = settings.refresh_interval_minutes * 60
    while True:
        logger.info("Scheduled refresh starting...")
        await update_all()
        logger.info(f"Scheduled refresh done. Next in {settings.refresh_interval_minutes}m")
        await asyncio.sleep(interval)
