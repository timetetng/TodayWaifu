from __future__ import annotations

from typing import Dict

from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsBoolConfig,
    GsStrConfig,
)

CONFIG_DEFAULT: Dict[str, GSC] = {
    'DailyWifeImageSource': GsStrConfig(
        '图片数据源',
        '选择 local 使用本地 XWUID 图片目录；选择 gallery 使用远程图库接口。图库图片可能存在内容风险，请自行决定是否启用；使用风险自行承担，插件作者不承担责任',
        'local',
        options=['local', 'gallery'],
    ),
    'DailyWifeCustomRolePilePath': GsStrConfig(
        '本地角色图片目录',
        '图片数据源为 local 时生效。留空时自动查找 gsuid_core/data/XutheringWavesUID/custom_role_pile',
        '',
    ),
    'DailyWifeRoleMapPath': GsStrConfig(
        '角色 ID 对照表路径',
        '留空时使用插件内置 wife_role_id_map.txt',
        '',
    ),
    'DailyWifeGalleryApiUrl': GsStrConfig(
        '图库接口地址',
        'XWUID 图库角色立绘接口地址，默认使用 https://img.xlinxc.cn/api/xwuid/roles。启用图库即表示已知晓图片内容风险并自行承担',
        'https://img.xlinxc.cn/api/xwuid/roles',
    ),
    'DailyWifeGalleryUsername': GsStrConfig(
        '图库账号',
        '访问 XWUID 图库接口和图片所需的账号。图库内容可能存在风险，请自行决定是否使用',
        '',
    ),
    'DailyWifeGalleryPassword': GsStrConfig(
        '图库密码',
        '访问 XWUID 图库接口和图片所需的密码。图库使用风险自行承担，插件作者不承担责任',
        '',
    ),
    'DailyWifeSendText': GsBoolConfig(
        '发送文字说明',
        '开启后图片前附带“你今天的老婆是xxx”',
        True,
    ),
    'DailyWifeReplyPrefixEnabled': GsBoolConfig(
        '启用回复前缀',
        '开启后插件回复会自动添加“[今日老婆]”前缀',
        True,
    ),
    'DailyWifeAtUser': GsBoolConfig(
        '发送时艾特触发者',
        '开启后发送今日老婆结果时会艾特触发者',
        True,
    ),
    'DailyWifeTextTemplate': GsStrConfig(
        '文字模板',
        '可用变量：{name} 角色名，{role_id} 数字 ID',
        '你今天的老婆是{name}',
    ),
}
