"""Pixiv API client + cache manager for TodayWaifu loli images."""

import json
import random
import shutil
import sys
import time
from pathlib import Path

# Ensure vendored pixivpy3 is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pixivpy'))

import requests
import urllib3
from pixivpy3 import AppPixivAPI
from pixivpy3.utils import PixivError
from requests_toolbelt.adapters import host_header_ssl

from .shared import _custom_upload_data_root, _cfg, logger, LOG_PREFIX

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MIN_CACHED_IMAGES = 10
_REFERSHING = False
_pximg_ip: str | None = None


def _pixiv_proxy() -> dict[str, str] | None:
    """Get proxy config for requests/cloudscraper."""
    proxy = str(_cfg('DailyWifePixivProxy') or '').strip()
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _pixiv_cache_root() -> Path:
    root = _custom_upload_data_root() / 'pixiv_cache'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _pixiv_manifest_path() -> Path:
    return _pixiv_cache_root() / 'manifest.json'


def _pixiv_cache_days() -> int:
    try:
        return max(1, int(_cfg('DailyWifePixivCacheDays')))
    except (TypeError, ValueError):
        return 3


def pixiv_enabled() -> bool:
    return bool(str(_cfg('DailyWifePixivRefreshToken') or '').strip())


def _load_manifest() -> dict:
    path = _pixiv_manifest_path()
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def _save_manifest(manifest: dict) -> None:
    _pixiv_manifest_path().write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _purge_expired(manifest: dict) -> dict:
    now = time.time()
    cache_days = _pixiv_cache_days()
    max_age = cache_days * 86400
    valid = {}
    all_valid_files: set[str] = set()

    for illust_id, entry in manifest.items():
        age = now - entry.get('downloaded_at', 0)
        if age < max_age:
            valid[illust_id] = entry
            all_valid_files.update(entry.get('files', []))
        else:
            for fname in entry.get('files', []):
                fpath = _pixiv_cache_root() / fname
                try:
                    fpath.unlink(missing_ok=True)
                except OSError:
                    pass

    root = _pixiv_cache_root()
    for f in root.iterdir():
        if f.is_file() and f.name != 'manifest.json' and f.name not in all_valid_files:
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass

    return valid


def pixiv_cached_paths() -> list[Path]:
    manifest = _load_manifest()
    manifest = _purge_expired(manifest)
    _save_manifest(manifest)
    root = _pixiv_cache_root()
    paths: list[Path] = []
    for entry in manifest.values():
        for fname in entry.get('files', []):
            fpath = root / fname
            if fpath.is_file():
                paths.append(fpath)
    return paths


def pixiv_cached_count() -> int:
    manifest = _load_manifest()
    manifest = _purge_expired(manifest)
    root = _pixiv_cache_root()
    count = 0
    for entry in manifest.values():
        for fname in entry.get('files', []):
            if (root / fname).is_file():
                count += 1
    return count


def pixiv_random_image() -> Path | None:
    manifest = _load_manifest()
    manifest = _purge_expired(manifest)
    _save_manifest(manifest)
    if not manifest:
        return None
    root = _pixiv_cache_root()
    illust_id = _pick_weighted(manifest)
    if illust_id is None:
        return None
    entry = manifest[illust_id]
    files = entry.get('files', [])
    if not files:
        return None
    fname = random.choice(files)
    fpath = root / fname
    return fpath if fpath.is_file() else None


def _pick_weighted(manifest: dict) -> str | None:
    entries = list(manifest.items())
    if not entries:
        return None
    illust_id, _ = random.choice(entries)
    return illust_id


def _resolve_pximg_ip() -> str:
    """Resolve i.pximg.net IP via DoH, cached globally."""
    global _pximg_ip
    if _pximg_ip:
        return _pximg_ip
    for doh in (
        "https://1.1.1.1/dns-query",
        "https://1.0.0.1/dns-query",
        "https://doh.dns.sb/dns-query",
        "https://cloudflare-dns.com/dns-query",
    ):
        try:
            resp = requests.get(
                doh,
                headers={"Accept": "application/dns-json"},
                params={"name": "i.pximg.net", "type": "A"},
                timeout=5,
            )
            ip = resp.json()["Answer"][0]["data"]
            _pximg_ip = ip
            return ip
        except Exception:
            continue
    msg = "Failed to resolve i.pximg.net via DoH"
    raise PixivError(msg)


def _pixiv_download(img_url: str, dest: str) -> None:
    """Download from i.pximg.net. Prefer proxy, fall back to DoH+IP direct."""
    headers = {
        "User-Agent": "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)",
        "Referer": "https://app-api.pixiv.net/",
    }
    proxy = _pixiv_proxy()
    # Attempt 1: use proxy (works when proxy can reach i.pximg.net)
    if proxy:
        try:
            logger.debug(f'{LOG_PREFIX} [Pixiv] 代理下载')
            resp = requests.get(img_url, headers=headers, timeout=60, stream=True, proxies=proxy)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp.raw, f)
            return
        except Exception as exc:
            logger.info(f'{LOG_PREFIX} [Pixiv] 代理下载失败，回退 DoH: {exc}')

    # Attempt 2: DoH-resolved IP + HostHeaderSSLAdapter (bypass proxy)
    logger.info(f'{LOG_PREFIX} [Pixiv] DoH 直连下载')
    ip = _resolve_pximg_ip()
    ip_url = img_url.replace("https://i.pximg.net", f"https://{ip}", 1)
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", host_header_ssl.HostHeaderSSLAdapter())
    headers["Host"] = "i.pximg.net"
    resp = session.get(ip_url, headers=headers, timeout=60, verify=False, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        shutil.copyfileobj(resp.raw, f)


def refresh_pixiv_cache() -> int:
    global _REFERSHING
    if _REFERSHING:
        logger.info(f'{LOG_PREFIX} [Pixiv] 已有刷新任务进行中，跳过')
        return 0
    _REFERSHING = True
    try:
        refresh_token = str(_cfg('DailyWifePixivRefreshToken') or '').strip()
        if not refresh_token:
            logger.info(f'{LOG_PREFIX} [Pixiv] 未配置 refresh_token，跳过')
            return 0

        tags = str(_cfg('DailyWifePixivSearchTags') or '萝莉 ロリ loli').strip()
        batch_size = 30
        try:
            batch_size = max(1, min(50, int(_cfg('DailyWifePixivMaxImages'))))
        except (TypeError, ValueError):
            pass

        proxy = _pixiv_proxy()
        logger.info(f'{LOG_PREFIX} [Pixiv] 刷新配置: tags="{tags}", batch={batch_size}, proxy={"有" if proxy else "无"}')

        manifest = _load_manifest()
        manifest = _purge_expired(manifest)
        existing_ids = set(manifest)
        logger.info(f'{LOG_PREFIX} [Pixiv] 当前缓存: {len(manifest)} 个作品')

        api = AppPixivAPI(proxies=proxy) if proxy else AppPixivAPI()
        api.auth(refresh_token=refresh_token)
        logger.info(f'{LOG_PREFIX} [Pixiv] 认证成功, user_id={api.user_id}')

        all_illusts: list[dict] = []
        for sort in ('date_desc', 'popular_desc'):
            try:
                url = f"{api.hosts}/v1/search/illust"
                params = {
                    "word": tags,
                    "search_target": "partial_match_for_tags",
                    "sort": sort,
                    "search_ai_type": 0,
                }
                r = api.no_auth_requests_call("GET", url, params=params)
                logger.info(f'{LOG_PREFIX} [Pixiv] sort={sort} HTTP {r.status_code}')
                result = api.parse_result(r)
                all_illusts = result.get('illusts', [])
                if all_illusts:
                    sample = all_illusts[0]
                    logger.info(f'{LOG_PREFIX} [Pixiv] 样例: id={sample.get("id")} bmk={sample.get("total_bookmarks")} x_restrict={sample.get("x_restrict")} ai_type={sample.get("ai_type")}')
                    logger.info(f'{LOG_PREFIX} [Pixiv] sort={sort} 返回 {len(all_illusts)} 个结果')
                    break
                else:
                    logger.warning(f'{LOG_PREFIX} [Pixiv] sort={sort} 返回空结果, keys={list(result.keys())}')
            except Exception as exc:
                logger.warning(f'{LOG_PREFIX} [Pixiv] sort={sort} 失败: {exc}')
                continue

        if not all_illusts:
            logger.warning(f'{LOG_PREFIX} [Pixiv] 搜索无结果')
            return 0

        filtered = [i for i in all_illusts if i.get('x_restrict', 0) == 0]
        logger.info(f'{LOG_PREFIX} [Pixiv] 过滤 R18: {len(all_illusts)} -> {len(filtered)}')
        filtered = [i for i in filtered if i.get('total_bookmarks', 0) >= 50]
        logger.info(f'{LOG_PREFIX} [Pixiv] 过滤低赞(>=50): -> {len(filtered)}')
        if filtered:
            logger.info(f'{LOG_PREFIX} [Pixiv] 过滤后样例: id={filtered[0].get("id")} bmk={filtered[0].get("total_bookmarks")}')
        if not filtered:
            bmks = sorted([i.get('total_bookmarks', 0) for i in all_illusts], reverse=True)[:10]
            xrs = [i.get('x_restrict', 0) for i in all_illusts]
            logger.warning(f'{LOG_PREFIX} [Pixiv] 全部被过滤! x_restrict分布: {set(xrs)} top10赞: {bmks}')
            return 0
        random.shuffle(filtered)
        illusts = filtered[:batch_size]
        logger.info(f'{LOG_PREFIX} [Pixiv] 最终选取 {len(illusts)} 个工作品下载')

        new_count = 0
        for idx, illust in enumerate(illusts, 1):
            illust_id = illust.get('id')
            if not illust_id or str(illust_id) in existing_ids:
                if str(illust_id) in existing_ids:
                    logger.debug(f'{LOG_PREFIX} [Pixiv] {illust_id} 已缓存，跳过')
                continue

            logger.info(f'{LOG_PREFIX} [Pixiv] [{idx}/{len(illusts)}] 下载作品 {illust_id} (bmk={illust.get("total_bookmarks", 0)})')
            meta_pages = illust.get('meta_pages', [])
            if meta_pages:
                urls = [
                    p.get('image_urls', {}).get('large', '')
                    or p.get('image_urls', {}).get('medium', '')
                    for p in meta_pages
                ]
            else:
                urls = [
                    illust.get('image_urls', {}).get('large', '')
                    or illust.get('image_urls', {}).get('medium', '')
                ]

            saved_files: list[str] = []
            for page_idx, img_url in enumerate(urls):
                if not img_url:
                    continue
                ext = Path(img_url.split('?')[0]).suffix or '.jpg'
                fname = f"{illust_id}_{page_idx}{ext}"
                fpath = _pixiv_cache_root() / fname
                try:
                    _pixiv_download(img_url, str(fpath))
                    if fpath.is_file():
                        saved_files.append(fname)
                        logger.info(f'{LOG_PREFIX} [Pixiv] ✓ {illust_id} p{page_idx} ({fpath.stat().st_size // 1024} KB)')
                except Exception as exc:
                    logger.warning(f'{LOG_PREFIX} [Pixiv] ✗ 下载失败 {illust_id} p{page_idx}: {exc}')
                    continue

            if saved_files:
                manifest[str(illust_id)] = {
                    "illust_id": illust_id,
                    "title": illust.get('title', ''),
                    "total_bookmarks": illust.get('total_bookmarks', 0),
                    "page_count": illust.get('page_count', 1),
                    "downloaded_at": time.time(),
                    "files": saved_files,
                }
                existing_ids.add(str(illust_id))
                new_count += 1

        if new_count > 0:
            _save_manifest(manifest)

        logger.info(f'{LOG_PREFIX} [Pixiv] 刷新缓存: 新增 {new_count} 张, 当前 {len(manifest)} 个作品')
        return new_count

    except Exception as exc:
        logger.warning(f'{LOG_PREFIX} [Pixiv] 刷新缓存失败: {exc}')
        return 0
    finally:
        _REFERSHING = False
