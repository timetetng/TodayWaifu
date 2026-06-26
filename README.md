# TodayWaifu

<p align="center">
  <a href="https://github.com/nnlmc/TodayWaifu"><img src="./ICON.png" width="160" alt="TodayWaifu ICON"></a>
</p>

<h1 align="center">TodayWaifu</h1>
<h4 align="center">GSCore / GsUID 用的鸣潮「今日老婆」插件</h4>

## 安装提醒

> 该插件为 [早柚核心(gsuid_core)](https://github.com/Genshin-bots/gsuid_core) 的扩展，需要先安装好 GSCore 才能使用。
>
> 插件交流、图库账号密码获取请加群：[798949533](https://qm.qq.com/q/ejzCUfJ5le)

## 功能

当前版本只保留最基础的 `今日老婆` 功能：

- 每个用户每天在同一群/私聊里固定抽到一个鸣潮老婆。
- 再次发送同一命令会返回当天已经抽到的老婆。
- 只发送角色结果，不再提供老公、群友、抢老婆、送老婆、萝莉图库、自定义老婆、帮助图、更新记录、总排行等功能。

## 命令

| 命令 | 说明 |
| --- | --- |
| `今日老婆` | 抽取当天老婆 |
| `娶婆娘` | `今日老婆` 的别名 |
| `jrlp` / `qlp` | `今日老婆` 的短别名 |

## 角色图片

角色图片由控制台「图片数据源」决定：

- `local`：读取本地 XWUID 图片目录。
- `gallery`：读取远程图库接口，需要配置图库账号密码。

本地模式默认查找：

```text
gsuid_core/data/XutheringWavesUID/custom_role_pile
gsuid_core/data/XutheringWavesUID/resource/role_pile
```

如不在默认位置，可用「本地角色图片目录」手动指定 `custom_role_pile` 路径。

注意：图库模式会从远程图库获取并发送图片，可能存在部分图片内容风险。是否启用请自行判断；因使用图库产生的任何风险由使用者自行承担，插件作者不承担责任。

## 常用配置

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| 图片数据源 | `local` | `local` 本地资源，`gallery` 远程图库接口 |
| 本地角色图片目录 | 空 | 本地模式生效，留空自动查找 XWUID 目录 |
| 角色 ID 对照表路径 | 空 | 留空使用内置 `wife_role_id_map.txt` |
| 图库接口地址 | `https://img.xlinxc.cn/api/xwuid/roles` | 图库模式生效 |
| 图库账号 / 图库密码 | 空 | 图库模式生效 |
| 发送文字说明 | 开启 | 图片前附带“你今天的老婆是xxx” |
| 启用回复前缀 | 开启 | 回复前添加「[今日老婆]」 |
| 发送时艾特触发者 | 开启 | 发送结果时艾特触发者 |
| 文字模板 | `你今天的老婆是{name}` | 支持 `{name}` 和 `{role_id}` |

## 数据

插件运行时数据写在 GSCore 的 `data/TodayWaifu/daily_wife_data.json`。

旧版本产生的其他功能数据不会再被读取；保留在数据文件里也不会影响当前基础功能。

## 其他

- 本项目仅供学习使用，请勿用于商业用途。
- 本项目采用 **GNU General Public License v3.0（GPLv3）** 开源。你可以使用、修改和分发，但需保留许可证与版权声明；分发修改版时按 GPLv3 继续开放对应源码。
