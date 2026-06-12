> 本项目采用 **GNU General Public License v3.0（GPLv3）** 开源。
>
> 你可以使用、修改和分发，但必须遵守 GPLv3：保留许可证与版权声明，分发修改版时按 GPLv3 继续开放对应源码。

# gs_wuwa_daily_wife

GSCore / GsUID 版鸣潮“今日老婆”插件。

插件支持两种图片数据源，可在控制台 `DailyWifeImageSource` 自由切换：

- `gallery`（默认）：使用 XWUID 画廊接口在线获取图片；
- `local`：读取本地角色图片目录，配合角色 ID 对照表抽取。

## 插件目录

```text
gs_wuwa_daily_wife
```

## 使用方法

固定触发命令：

```text
今日老婆
老婆列表
今日老公   # 需在控制台开启 DailyWifeHusbandEnabled
老公列表   # 需在控制台开启 DailyWifeHusbandEnabled
```

插件禁用 GSCore 强制前缀继承，直接发送 `今日老婆` 即可触发。

触发后，插件会按当天日期、用户 ID 和当前群号固定随机一个结果；同一个用户在不同群会分别固定，不再跨群同步。

`今日老婆` 只抽女角色，`今日老公` 只抽男角色，两者每日结果相互独立、分别固定。

发送 `老婆列表` / `今日老婆列表`（或 `老公列表` / `今日老公列表`）可以查看当前群今天已有记录，不会发送图片。

抽取流程：

**画廊接口模式（`DailyWifeImageSource=gallery`）**

1. 请求 `DailyWifeGalleryApiUrl` 配置的 XWUID 画廊接口；
2. 过滤男角色和所有名字包含 `漂泊者` 的角色；
3. 从保留角色中随机一个角色；
4. 只使用该角色的 `角色立绘` 图片列表；
5. 随机下载一张图片并发送。

画廊接口和图片路径都需要账号密码。插件会用控制台配置的画廊账号密码请求接口和下载图片，然后以图片字节发送，不会把账号密码拼进图片 URL。

**本地目录模式（`DailyWifeImageSource=local`）**

1. 读取 `DailyWifeRoleMapPath` 配置的角色 ID 对照表（留空则用插件内置 `role_id_map.txt`）；
2. 在 `DailyWifeCustomRolePilePath` 配置的图片目录里，按对照表的角色 ID 查找对应子目录（留空则自动查找 `gsuid_core/data/XutheringWavesUID/custom_role_pile`）；
3. 过滤男角色和所有名字包含 `漂泊者` 的角色；
4. 从有图片的角色中随机一个，再随机一张本地图片直接发送。

本地目录结构示例（子目录名为角色数字 ID）：

```text
custom_role_pile/
├── 1211/        # 达妮娅
│   ├── a.png
│   └── b.jpg
└── 1304/        # 今汐
    └── c.png
```

对照表格式为每行 `ID：角色名`，例如 `1211：达妮娅`。

## 控制台配置

- `DailyWifeImageSource`：图片数据源，`gallery`（默认）或 `local`；
- `DailyWifeCustomRolePilePath`：本地角色图片目录，数据源为 `local` 时生效，留空自动查找；
- `DailyWifeRoleMapPath`：本地角色 ID 对照表路径，数据源为 `local` 时生效，留空用内置表；
- `DailyWifeGalleryApiUrl`：画廊接口地址，默认 `https://img.xlinxc.cn/api/xwuid/roles`；
- `DailyWifeGalleryUsername`：画廊账号；
- `DailyWifeGalleryPassword`：画廊密码；
- `DailyWifeSendText`：是否发送“你今天的老婆是xxx”；
- `DailyWifeAtUser`：发送今日老婆和抢老婆成功图片时是否艾特对应用户；
- `DailyWifeShowRoleId`：是否显示角色 ID；
- `DailyWifeTextTemplate`：文字模板，可用变量 `{name}`、`{role_id}`；
- `DailyWifeHusbandEnabled`：是否启用「今日老公」命令，默认关闭，开启后只抽男角色；
- `DailyHusbandTextTemplate`：今日老公文字模板，可用变量 `{name}`、`{role_id}`；
- `DailyWifeMasterUnlimited`：主人无限抽老婆，开启后 GSCore 主人不会固定当天结果；
- `DailyWifeRobEnabled`：是否启用抢老婆命令；
- `DailyWifeRobSuccessRate`：抢老婆成功概率；
- `DailyWifeRobSuccessTemplate`：抢老婆成功提示，可用变量 `{name}`、`{role_id}`、`{target}`。

## 今日老公

在控制台开启 `DailyWifeHusbandEnabled` 后，可使用 `今日老公` / `老公列表` 命令，只抽取男角色，规则与今日老婆一致。

- 画廊接口模式下，男角色由接口返回的角色名自动识别；
- 本地目录模式下，需要在角色 ID 对照表里包含男角色 ID，且对应目录下有图片，否则会提示「没有找到可用的老公角色」。插件内置的 `role_id_map.txt` 默认只收录了女角色，如需本地老公请在 `DailyWifeRoleMapPath` 指定的对照表里自行补充男角色 ID。

## 抢老婆

使用 `wl抢老婆 @对方` 或 `wl抢老婆 对方QQ` 可以抢别人今天在当前群抽到的老婆。

- 控制台关闭 `DailyWifeRobEnabled` 后，抢老婆命令不会继续执行；
- 普通用户每天只能抢一次；
- 机器人主人不受次数限制；
- 目标用户当天必须已经在当前群发送过 `今日老婆`；
- 抢老婆有成功/失败概率；
- 失败提示固定为：`抢老婆失败了，还被对方痛扁了一顿！`；
- 成功后，自己的今日老婆会被替换成对方今天记录里的老婆，并发送对方记录里的同一张图片。

## 账号发放

画廊账号密码由管理员单独发放。用户拿到账号密码后，在插件控制台填写 `DailyWifeGalleryUsername` 和 `DailyWifeGalleryPassword` 即可。
