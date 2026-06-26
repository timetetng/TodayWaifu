"""TodayWaifu shared utilities.

只保留「今日老婆」基础抽取能力：加载角色、保存当天结果、发送图片。
"""
from __future__ import annotations

import asyncio
import base64
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gsuid_core.bot import Bot
from gsuid_core.data_store import get_res_path
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import Plugins, SV

from ..daily_wife_config import DailyWifeConfig

Plugins(
    name='TodayWaifu',
    disable_force_prefix=True,
    allow_empty_prefix=True,
)

sv = SV('鸣潮今日老婆')

BASE_DIR = Path(__file__).parent.parent
WIFE_ROLE_MAP_PATH = BASE_DIR / 'wife_role_id_map.txt'
DEFAULT_GALLERY_API_URL = 'https://img.xlinxc.cn/api/xwuid/roles'
CACHE_TTL_SECONDS = 300

LOG_PREFIX = '[鸣潮今日老婆]'
REPLY_PREFIX = '[今日老婆]'
ROLE_MAP_RE = re.compile(r'^\s*(\d+)\s*[:：]\s*(.+?)\s*$')
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
CANDIDATE_CACHE: dict[str, tuple[float, tuple['RoleCandidate', ...]]] = {}


@dataclass(frozen=True)
class RoleCandidate:
    name: str
    role_ids: tuple[str, ...]
    images: tuple[str, ...]


@dataclass(frozen=True)
class WifeRecord:
    name: str
    role_ids: tuple[str, ...]
    image: str

    @classmethod
    def from_role(cls, role: RoleCandidate, image: str) -> 'WifeRecord':
        return cls(role.name, role.role_ids, image)

    def to_role(self) -> RoleCandidate:
        return RoleCandidate(self.name, self.role_ids, (self.image,))


def _cfg(key: str, default: Any = None) -> Any:
    try:
        value = DailyWifeConfig.get_config(key).data
    except Exception:
        return default
    return default if value is None else value


def _cfg_bool(key: str, default: bool = False) -> bool:
    value = _cfg(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {'true', '1', 'yes', 'y', 'on', 'enable', 'enabled', '开启'}:
            return True
        if text in {'false', '0', 'no', 'n', 'off', 'disable', 'disabled', '关闭'}:
            return False
    return default


def _image_source() -> str:
    value = str(_cfg('DailyWifeImageSource', 'local') or 'local').strip().lower()
    return 'gallery' if value == 'gallery' else 'local'


def _configured_path(key: str) -> Path | None:
    raw = str(_cfg(key, '') or '').strip().strip('"')
    if not raw:
        return None
    return Path(raw).expanduser()


def _data_root() -> Path:
    return get_res_path('TodayWaifu')


def _wife_data_path() -> Path:
    return _data_root() / 'daily_wife_data.json'


def _load_wife_data() -> dict[str, Any]:
    path = _wife_data_path()
    if not path.is_file():
        return {'days': {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        logger.warning(f'{LOG_PREFIX} 读取数据文件失败: {exc}')
        return {'days': {}}
    if not isinstance(data, dict):
        return {'days': {}}
    data.setdefault('days', {})
    return data


def _save_wife_data(data: dict[str, Any]) -> None:
    try:
        path = _wife_data_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as exc:
        logger.error(f'{LOG_PREFIX} 保存数据文件失败: {exc}')


def _today_key() -> str:
    return date.today().isoformat()


def _context_key(ev: Event) -> str:
    return f'{ev.bot_id}:{ev.group_id or "direct"}'


def _get_today_context(data: dict[str, Any], ev: Event) -> dict[str, Any]:
    day = data.setdefault('days', {}).setdefault(_today_key(), {})
    context = day.setdefault(_context_key(ev), {})
    context.setdefault('wives', {})
    return context


def _user_key(ev: Event, user_id: str | int | None = None) -> str:
    return str(ev.user_id if user_id is None else user_id)


def _daily_rng(ev: Event, user_id: str | int | None = None) -> random.Random:
    group_key = ev.group_id or 'direct'
    target_user_id = ev.user_id if user_id is None else user_id
    seed = f'{date.today().isoformat()}:{target_user_id}:{group_key}'
    logger.debug(f'{LOG_PREFIX} 生成随机数种子: {seed}')
    return random.Random(seed)


def _record_to_dict(record: WifeRecord, ev: Event, user_id: str | int) -> dict[str, Any]:
    return {
        'name': record.name,
        'role_ids': list(record.role_ids),
        'image': record.image,
        'record_type': 'role',
        'user_id': str(user_id),
        'updated_at': int(time.time()),
    }


def _record_from_dict(raw: Any) -> WifeRecord | None:
    if not isinstance(raw, dict):
        return None
    if str(raw.get('record_type') or 'role') != 'role':
        return None
    name = str(raw.get('name') or '').strip()
    image = str(raw.get('image') or '').strip()
    role_ids = tuple(str(item).strip() for item in raw.get('role_ids') or () if str(item).strip())
    if not name or not image:
        return None
    return WifeRecord(name=name, role_ids=role_ids, image=image)


def _resolve_role_map_path() -> Path | None:
    candidates = [
        _configured_path('DailyWifeRoleMapPath'),
        _configured_path('DailyWifeWifeRoleMapPath'),
        WIFE_ROLE_MAP_PATH,
    ]
    for path in candidates:
        if path and path.is_file():
            logger.debug(f'{LOG_PREFIX} 使用角色对照表: {path}')
            return path
    logger.warning(f'{LOG_PREFIX} 未找到今日老婆角色 ID 对照表')
    return None


def _load_role_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        match = ROLE_MAP_RE.match(line)
        if not match:
            continue
        role_id, role_name = match.groups()
        role_name = role_name.strip()
        if role_name:
            result[role_id] = role_name
    return result


def _load_wife_role_map() -> dict[str, str]:
    path = _resolve_role_map_path()
    return _load_role_map(path) if path else {}


def _resolve_xwuid_custom_pile_root() -> Path | None:
    configured = _configured_path('DailyWifeCustomRolePilePath')
    candidates = [configured] if configured else []
    candidates.extend(
        [
            Path.cwd() / 'gsuid_core' / 'data' / 'XutheringWavesUID' / 'custom_role_pile',
            Path.cwd() / 'data' / 'XutheringWavesUID' / 'custom_role_pile',
            BASE_DIR.parent / 'gsuid_core' / 'data' / 'XutheringWavesUID' / 'custom_role_pile',
            BASE_DIR.parent / 'data' / 'XutheringWavesUID' / 'custom_role_pile',
        ]
    )
    try:
        import gsuid_core

        core_root = Path(gsuid_core.__file__).resolve().parents[1]
        candidates.append(core_root / 'data' / 'XutheringWavesUID' / 'custom_role_pile')
    except Exception:
        pass

    for path in candidates:
        if path and path.is_dir():
            return path
    return None


def _resolve_default_role_pile_root() -> Path | None:
    candidates = [
        Path.cwd() / 'gsuid_core' / 'data' / 'XutheringWavesUID' / 'resource' / 'role_pile',
        Path.cwd() / 'data' / 'XutheringWavesUID' / 'resource' / 'role_pile',
        BASE_DIR.parent / 'gsuid_core' / 'data' / 'XutheringWavesUID' / 'resource' / 'role_pile',
        BASE_DIR.parent / 'data' / 'XutheringWavesUID' / 'resource' / 'role_pile',
    ]
    try:
        import gsuid_core

        core_root = Path(gsuid_core.__file__).resolve().parents[1]
        candidates.append(core_root / 'data' / 'XutheringWavesUID' / 'resource' / 'role_pile')
    except Exception:
        pass

    for path in candidates:
        if path and path.is_dir():
            return path
    return None


def _role_images(role_dir: Path) -> tuple[str, ...]:
    images = [
        path
        for path in role_dir.rglob('*')
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return tuple(str(path) for path in sorted(images, key=lambda item: str(item).lower()))


def _collect_local_candidates(
    role_map: dict[str, str],
    custom_root: Path | None,
    default_root: Path | None,
) -> tuple[RoleCandidate, ...]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for role_id in sorted(role_map.keys(), key=lambda item: int(item) if item.isdigit() else item):
        role_name = role_map[role_id]
        images: list[str] = []

        if custom_root and custom_root.is_dir():
            role_dir = custom_root / role_id
            if role_dir.is_dir():
                images.extend(_role_images(role_dir))

        if not images and default_root and default_root.is_dir():
            for ext in IMAGE_EXTENSIONS:
                fallback = default_root / f'role_pile_{role_id}{ext}'
                if fallback.is_file():
                    images.append(str(fallback))
                    break

        if not images:
            continue

        bucket = grouped.setdefault(role_name, {'role_ids': [], 'images': []})
        bucket['role_ids'].append(role_id)
        bucket['images'].extend(images)

    candidates = [
        RoleCandidate(
            name=name,
            role_ids=tuple(bucket['role_ids']),
            images=tuple(bucket['images']),
        )
        for name, bucket in grouped.items()
    ]
    return tuple(sorted(candidates, key=lambda item: item.name))


def _load_local_candidates() -> tuple[tuple[RoleCandidate, ...] | None, str | None]:
    role_map = _load_wife_role_map()
    if not role_map:
        return None, '没有找到鸣潮老婆角色 ID 对照表。'

    custom_root = _resolve_xwuid_custom_pile_root()
    default_root = _resolve_default_role_pile_root()
    if custom_root is None and default_root is None:
        return None, '没有找到 XWUID 角色图片目录。'

    candidates = _collect_local_candidates(role_map, custom_root, default_root)
    if not candidates:
        return None, '图片目录里没有找到可用的老婆图片。'
    logger.info(f'{LOG_PREFIX} 成功从本地加载候选角色 {len(candidates)} 名')
    return candidates, None


def _gallery_api_url() -> str:
    return str(_cfg('DailyWifeGalleryApiUrl', DEFAULT_GALLERY_API_URL) or DEFAULT_GALLERY_API_URL).strip()


def _gallery_auth_header() -> str | None:
    username = str(_cfg('DailyWifeGalleryUsername', '') or '').strip()
    password = str(_cfg('DailyWifeGalleryPassword', '') or '').strip()
    if not username or not password:
        return None
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def _request_headers() -> dict[str, str]:
    headers = {'User-Agent': 'TodayWaifu/1.0'}
    auth = _gallery_auth_header()
    if auth:
        headers['Authorization'] = auth
    return headers


def _http_get(url: str, *, timeout: int = 15) -> bytes:
    request = Request(url, headers=_request_headers())
    with urlopen(request, timeout=timeout) as resp:
        return resp.read()


def _fetch_gallery_payload_sync() -> dict[str, Any]:
    try:
        body = _http_get(_gallery_api_url(), timeout=15)
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError('图库账号或密码不正确，接口返回 401。') from exc
        raise RuntimeError(f'请求图库接口失败，HTTP {exc.code}。') from exc
    except URLError as exc:
        raise RuntimeError(f'请求图库接口失败：{exc.reason}') from exc
    except TimeoutError as exc:
        raise RuntimeError('请求图库接口超时。') from exc

    try:
        payload = json.loads(body.decode('utf-8'))
    except Exception as exc:
        raise RuntimeError('图库接口返回内容不是有效 JSON。') from exc
    if not isinstance(payload, dict):
        raise RuntimeError('图库接口返回格式不正确。')
    return payload


def _parse_gallery_candidates(payload: dict[str, Any], role_map: dict[str, str]) -> tuple[RoleCandidate, ...]:
    roles_data = payload.get('roles')
    if not isinstance(roles_data, list):
        return ()

    candidates: list[RoleCandidate] = []
    for item in roles_data:
        if not isinstance(item, dict):
            continue

        role_ids = tuple(str(role_id).strip() for role_id in item.get('role_ids') or [] if str(role_id).strip())
        allowed_ids = tuple(role_id for role_id in role_ids if role_id in role_map)
        if not allowed_ids:
            continue

        images: list[str] = []
        for image_item in item.get('images') or []:
            url = str(image_item.get('url') if isinstance(image_item, dict) else image_item or '').strip()
            if url.startswith(('http://', 'https://')):
                images.append(url)

        if images:
            candidates.append(
                RoleCandidate(
                    name=role_map[allowed_ids[0]],
                    role_ids=allowed_ids,
                    images=tuple(images),
                )
            )

    return tuple(sorted(candidates, key=lambda role: role.name))


def _load_gallery_candidates_sync() -> tuple[tuple[RoleCandidate, ...] | None, str | None]:
    role_map = _load_wife_role_map()
    if not role_map:
        return None, '没有找到鸣潮老婆角色 ID 对照表。'

    try:
        payload = _fetch_gallery_payload_sync()
        candidates = _parse_gallery_candidates(payload, role_map)
    except RuntimeError as exc:
        logger.warning(f'{LOG_PREFIX} 读取图库接口失败: {exc}')
        return None, str(exc)
    except Exception as exc:
        logger.warning(f'{LOG_PREFIX} 读取图库接口异常: {exc}')
        return None, '读取图库接口失败。'

    if not candidates:
        return None, '图库接口里没有找到可用的老婆图片。'
    logger.info(f'{LOG_PREFIX} 成功从图库加载候选角色 {len(candidates)} 名')
    return candidates, None


async def _load_candidates() -> tuple[tuple[RoleCandidate, ...] | None, str | None]:
    source = _image_source()
    now = time.time()
    cached = CANDIDATE_CACHE.get(source)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1], None

    if source == 'gallery':
        candidates, error = await asyncio.to_thread(_load_gallery_candidates_sync)
    else:
        candidates, error = await asyncio.to_thread(_load_local_candidates)

    if error or not candidates:
        return None, error
    CANDIDATE_CACHE[source] = (now, candidates)
    return candidates, None


def _download_image_sync(url: str) -> bytes:
    try:
        return _http_get(url, timeout=20)
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError('图库账号或密码不正确，图片返回 401。') from exc
        raise RuntimeError(f'下载图片失败，HTTP {exc.code}。') from exc
    except URLError as exc:
        raise RuntimeError(f'下载图片失败：{exc.reason}') from exc
    except TimeoutError as exc:
        raise RuntimeError('下载图片超时。') from exc


async def _download_image(url: str) -> bytes:
    return await asyncio.to_thread(_download_image_sync, url)


def _reply_text(text: str) -> str:
    return f'{REPLY_PREFIX}{text}'


def _prefix_outgoing_message(message: Any) -> Any:
    if isinstance(message, str):
        return _reply_text(message)
    if isinstance(message, list):
        result = list(message)
        for index, item in enumerate(result):
            if isinstance(item, str) and item.strip():
                result[index] = _reply_text(item)
                return result
        return [_reply_text(''), *result]
    return [_reply_text(''), message]


async def _send_prefixed(bot: Bot, message: Any, *args: Any, **kwargs: Any) -> Any:
    if not _cfg_bool('DailyWifeReplyPrefixEnabled', True):
        return await bot.send(message, *args, **kwargs)
    return await bot.send(_prefix_outgoing_message(message), *args, **kwargs)


async def _send_role_image(
    bot: Bot,
    role: RoleCandidate,
    image_ref: str,
    text: str | None = None,
    user_id: str | int | None = None,
) -> None:
    if image_ref.startswith(('http://', 'https://')):
        try:
            image: Any = await _download_image(image_ref)
        except RuntimeError as exc:
            await _send_prefixed(bot, str(exc))
            return
    else:
        path = Path(image_ref)
        if not path.is_file():
            await _send_prefixed(bot, '本地图片文件不存在，请检查 XWUID 角色图片目录。')
            return
        image = path

    messages: list[Any] = []
    if user_id is not None and _cfg_bool('DailyWifeAtUser', True):
        messages.append(MessageSegment.at(user_id))
        messages.append('\n')
    if text:
        messages.append(text)
    messages.append(MessageSegment.image(image))
    await _send_prefixed(bot, messages if len(messages) > 1 else messages[0])
