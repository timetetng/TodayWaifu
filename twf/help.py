"""TodayWaifu - help module."""
from __future__ import annotations

from .shared import *  # noqa: F403


@sv.on_fullmatch('今日老婆帮助', block=True)
async def daily_wife_help(bot: Bot, ev: Event):
    if not HELP_IMAGE_PATH.is_file():
        logger.warning(f'{LOG_PREFIX} 帮助图片不存在: {HELP_IMAGE_PATH}')
        return await bot.send('帮助图片缺失，请联系管理员。')
    await bot.send(MessageSegment.image(HELP_IMAGE_PATH))



# 注册到 GsCore 帮助一览页（core帮助）
# icon 必须是带 alpha 的方形小图标，否则核心合成帮助图时会报 bad transparency mask
if HELP_ICON_PATH.is_file():
    try:
        with Image.open(HELP_ICON_PATH) as _help_icon:
            register_help('TodayWaifu', '今日老婆帮助', _help_icon.convert('RGBA'))
    except Exception as exc:
        logger.warning(f'{LOG_PREFIX} 注册插件帮助失败: {exc}')
