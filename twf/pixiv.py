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
_pximg_direct: bool | None = None


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


def _probe_direct_download() -> None:
    """Probe once whether normal HTTPS download works, cache the result globally."""
    global _pximg_direct
    if _pximg_direct is not None:
        return
    url = "https://i.pximg.net/c/100x100_80_a2/img-master/img/2020/01/01/00/00/00/1_p0_master1200.jpg"
    proxy = _pixiv_proxy()
    try:
        resp = requests.get(url, headers={"Referer": "https://app-api.pixiv.net/"}, timeout=8, proxies=proxy)
        _pximg_direct = resp.status_code == 200
    except Exception:
        _pximg_direct = False
    logger.info(f'{LOG_PREFIX} [Pixiv] 直连下载可用: {_pximg_direct}')


def _pixiv_download(img_url: str, dest: str) -> None:
    """Download from i.pximg.net. Use direct or DoH+IP based on probe result."""
    _probe_direct_download()
    headers = {
        "User-Agent": "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)",
        "Referer": "https://app-api.pixiv.net/",
    }
    proxy = _pixiv_proxy()
    if _pximg_direct:
        resp = requests.get(img_url, headers=headers, timeout=30, stream=True, proxies=proxy)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp.raw, f)
        return

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
        return 0
    _REFERSHING = True
    try:
        refresh_token = str(_cfg('DailyWifePixivRefreshToken') or '').strip()
        if not refresh_token:
            return 0

        tags = str(_cfg('DailyWifePixivSearchTags') or '萝莉 ロリ loli').strip()
        batch_size = 30
        try:
            batch_size = max(1, min(50, int(_cfg('DailyWifePixivMaxImages'))))
        except (TypeError, ValueError):
            pass

        manifest = _load_manifest()
        manifest = _purge_expired(manifest)
        existing_ids = set(manifest)

        proxy = _pixiv_proxy()
        api = AppPixivAPI(proxies=proxy) if proxy else AppPixivAPI()
        api.auth(refresh_token=refresh_token)

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
                result = api.parse_result(r)
                all_illusts = result.get('illusts', [])
                if all_illusts:
                    break
            except Exception as exc:
                logger.debug(f'{LOG_PREFIX} [Pixiv] sort={sort} 失败: {exc}')
                continue

        if not all_illusts:
            logger.info(f'{LOG_PREFIX} [Pixiv] 搜索无结果')
            return 0

        filtered = [i for i in all_illusts if i.get('x_restrict', 0) == 0]
        filtered = [i for i in filtered if i.get('total_bookmarks', 0) >= 50]
        random.shuffle(filtered)
        illusts = filtered[:batch_size]
        logger.debug(f'{LOG_PREFIX} [Pixiv] 搜索 {len(all_illusts)} -> 过滤后 {len(filtered)} -> 取 {len(illusts)}')

        new_count = 0
        for illust in illusts:
            illust_id = illust.get('id')
            if not illust_id or str(illust_id) in existing_ids:
                continue

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
                except Exception as exc:
                    logger.warning(f'{LOG_PREFIX} [Pixiv] 下载失败 {illust_id} p{page_idx}: {exc}')
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
