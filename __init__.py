"""TodayWaifu - 鸣潮今日老婆 GsCore 插件。

当前版本只保留最基础的「今日老婆」功能。
"""
from gsuid_core.sv import Plugins

Plugins(
    name='TodayWaifu',
    disable_force_prefix=True,
    allow_empty_prefix=True,
)

from .twf import shared  # 公共层：SV 实例、配置、数据和图片工具  # noqa: F401
from .twf import daily   # 今日老婆命令注册  # noqa: F401
