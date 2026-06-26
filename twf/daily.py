"""TodayWaifu daily command.

只保留最基础的「今日老婆」：每天每个群/私聊里每个用户固定一个老婆。
"""
from __future__ import annotations

from .shared import (
    Bot,
    Event,
    LOG_PREFIX,
    RoleCandidate,
    WifeRecord,
    _cfg,
    _cfg_bool,
    _daily_rng,
    _get_today_context,
    _load_candidates,
    _load_wife_data,
    _record_from_dict,
    _record_to_dict,
    _save_wife_data,
    _send_prefixed,
    _send_role_image,
    _user_key,
    logger,
    sv,
)


def _build_text(role: RoleCandidate) -> str:
    template = str(_cfg('DailyWifeTextTemplate', '你今天的老婆是{name}') or '你今天的老婆是{name}')
    return template.format(name=role.name, role_id='/'.join(role.role_ids))


async def _ensure_daily_wife_record(ev: Event) -> WifeRecord | None:
    key = _user_key(ev)

    data = _load_wife_data()
    context = _get_today_context(data, ev)
    current = context['wives'].get(key)
    if isinstance(current, dict):
        record = _record_from_dict(current)
        if record is not None:
            logger.debug(f'{LOG_PREFIX} 命中已有今日老婆记录: {record.name}')
            return record

    candidates, error = await _load_candidates()
    if error or not candidates:
        logger.error(f'{LOG_PREFIX} 获取候选列表失败: {error}')
        return None

    rng = _daily_rng(ev, key)
    role = rng.choice(candidates)
    image = rng.choice(role.images)
    record = WifeRecord.from_role(role, image)

    data = _load_wife_data()
    context = _get_today_context(data, ev)
    existing = context['wives'].get(key)
    if isinstance(existing, dict):
        existing_record = _record_from_dict(existing)
        if existing_record is not None:
            return existing_record

    context['wives'][key] = _record_to_dict(record, ev, key)
    _save_wife_data(data)
    logger.info(f'{LOG_PREFIX} 为用户 {key} 生成今日老婆: {record.name}')
    return record


async def _send_daily_wife(bot: Bot, ev: Event) -> None:
    logger.info(f'{LOG_PREFIX} 用户 {ev.user_id} 在群 {ev.group_id or "direct"} 请求今日老婆')

    record = await _ensure_daily_wife_record(ev)
    if record is None:
        return await _send_prefixed(bot, '没有找到可用的老婆角色。')

    text = _build_text(record.to_role()) if _cfg_bool('DailyWifeSendText', True) else None
    await _send_role_image(bot, record.to_role(), record.image, text, ev.user_id)


@sv.on_fullmatch(('今日老婆', '娶婆娘', 'jrlp', 'qlp'), block=True)
async def daily_wife(bot: Bot, ev: Event):
    await _send_daily_wife(bot, ev)
