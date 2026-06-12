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
        '填 gallery 使用画廊接口（默认）；填 local 使用本地图片目录读取',
        'gallery',
    ),
    'DailyWifeCustomRolePilePath': GsStrConfig(
        '本地角色图片目录',
        '数据源为 local 时生效。留空时自动查找 gsuid_core/data/XutheringWavesUID/custom_role_pile；也可以手动填写绝对路径',
        '',
    ),
    'DailyWifeRoleMapPath': GsStrConfig(
        '本地角色 ID 对照表路径',
        '数据源为 local 时生效。留空时优先使用插件内置 role_id_map.txt；也可以手动填写自己的对照表路径',
        '',
    ),
    'DailyWifeGalleryApiUrl': GsStrConfig(
        '画廊接口地址',
        'XWUID 画廊角色立绘接口地址，默认使用 https://img.xlinxc.cn/api/xwuid/roles',
        'https://img.xlinxc.cn/api/xwuid/roles',
    ),
    'DailyWifeGalleryUsername': GsStrConfig(
        '画廊账号',
        '访问 XWUID 画廊接口和图片所需的账号',
        '',
    ),
    'DailyWifeGalleryPassword': GsStrConfig(
        '画廊密码',
        '访问 XWUID 画廊接口和图片所需的密码',
        '',
    ),
    'DailyWifeSendText': GsBoolConfig(
        '发送文字说明',
        '开启后图片前附带“你今天的老婆是xxx”',
        True,
    ),
    'DailyWifeAtUser': GsBoolConfig(
        '发送时艾特触发者',
        '开启后发送今日老婆和抢老婆成功图片时会艾特对应用户',
        True,
    ),
    'DailyWifeShowRoleId': GsBoolConfig(
        '显示角色 ID',
        '开启后在文字说明里额外显示本次角色对应的数字 ID',
        False,
    ),
    'DailyWifeTextTemplate': GsStrConfig(
        '文字模板',
        '可用变量：{name} 角色名，{role_id} 数字 ID',
        '你今天的老婆是{name}',
    ),
    'DailyWifeHusbandEnabled': GsBoolConfig(
        '启用今日老公',
        '开启后可使用「今日老公」命令，只抽取男角色；关闭后命令不生效',
        False,
    ),
    'DailyHusbandTextTemplate': GsStrConfig(
        '今日老公文字模板',
        '今日老公的文字说明模板，可用变量：{name} 角色名，{role_id} 数字 ID',
        '你今天的老公是{name}',
    ),
    'DailyWifeMasterUnlimited': GsBoolConfig(
        '主人无限抽老婆',
        '开启后，GSCore 主人触发今日老婆时不再按每日固定结果，可重复随机抽取',
        True,
    ),
    'DailyWifeRobEnabled': GsBoolConfig(
        '启用抢老婆',
        '关闭后抢老婆命令不再生效',
        True,
    ),
    'DailyWifeRobSuccessRate': GsStrConfig(
        '抢老婆成功概率',
        '0 到 1 之间的小数，例如 0.5 表示 50% 成功。普通用户每天一次，机器人主人不受次数限制',
        '0.5',
    ),
    'DailyWifeRobSuccessTemplate': GsStrConfig(
        '抢老婆成功提示',
        '可用变量：{name} 角色名，{role_id} 数字 ID，{target} 被抢用户 ID',
        '抢老婆成功！你把对方今天的老婆{name}抢过来了！',
    ),
}
