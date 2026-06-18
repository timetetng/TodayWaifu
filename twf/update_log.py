"""TodayWaifu - update_log module."""
from __future__ import annotations

from .shared import *  # noqa: F403


def _github_update_api_url() -> str:
    url = str(_cfg('DailyWifeUpdateLogApiUrl') or GITHUB_UPDATE_API_URL).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise RuntimeError('老婆更新记录接口地址无效，请检查 DailyWifeUpdateLogApiUrl 配置。')
    return url


def _github_update_limit() -> int:
    try:
        value = int(_cfg('DailyWifeUpdateLogLimit'))
    except (TypeError, ValueError):
        value = 6
    return max(1, min(12, value))


def _github_update_headers() -> dict[str, str]:
    return {
        'User-Agent': 'TodayWaifu/1.0',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def _github_update_fetch_sync() -> tuple[GitHubUpdateRecord, ...]:
    request = Request(_github_update_api_url(), headers=_github_update_headers())
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read(512 * 1024 + 1)
    except HTTPError as exc:
        if exc.code == 403:
            raise RuntimeError('GitHub 更新记录接口访问受限或频率过高，请稍后再试。') from exc
        if exc.code == 404:
            raise RuntimeError('GitHub 更新记录接口不存在，请检查仓库地址。') from exc
        raise RuntimeError(f'获取 GitHub 更新记录失败，HTTP {exc.code}。') from exc
    except URLError as exc:
        raise RuntimeError(f'获取 GitHub 更新记录失败：{exc.reason}') from exc
    except TimeoutError as exc:
        raise RuntimeError('获取 GitHub 更新记录超时。') from exc

    if len(body) > 512 * 1024:
        raise RuntimeError('GitHub 更新记录返回内容过大。')

    try:
        payload = json.loads(body.decode('utf-8'))
    except Exception as exc:
        raise RuntimeError('GitHub 更新记录返回内容不是有效 JSON。') from exc

    if isinstance(payload, dict):
        message = str(payload.get('message') or '').strip()
        if message:
            raise RuntimeError(f'GitHub 更新记录接口返回错误：{message}')
    if not isinstance(payload, list):
        raise RuntimeError('GitHub 更新记录返回格式不正确。')

    records = _parse_github_update_records(payload)
    if not records:
        raise RuntimeError('没有获取到可展示的 GitHub 更新记录。')
    return records


def _parse_github_update_records(payload: list[Any]) -> tuple[GitHubUpdateRecord, ...]:
    records: list[GitHubUpdateRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        commit = item.get('commit')
        if not isinstance(commit, dict):
            continue

        raw_message = str(commit.get('message') or '').strip()
        if not raw_message:
            continue
        message = raw_message.splitlines()[0].strip()

        author_data = commit.get('author') if isinstance(commit.get('author'), dict) else {}
        committer_data = commit.get('committer') if isinstance(commit.get('committer'), dict) else {}
        github_author = item.get('author') if isinstance(item.get('author'), dict) else {}
        author = str(
            github_author.get('login')
            or author_data.get('name')
            or committer_data.get('name')
            or 'unknown'
        )
        updated_at = str(author_data.get('date') or committer_data.get('date') or '')
        sha = str(item.get('sha') or '')
        url = str(item.get('html_url') or '')
        records.append(
            GitHubUpdateRecord(
                message=message,
                sha=sha[:7],
                author=author,
                updated_at=updated_at,
                url=url,
            )
        )
    return tuple(records)


def _select_github_update_records(records: tuple[GitHubUpdateRecord, ...]) -> tuple[GitHubUpdateRecord, ...]:
    # GitHub commits 接口本身按时间倒序返回，直接取最新 N 条，不打乱顺序
    return records[:_github_update_limit()]


def _format_github_update_time(value: str) -> str:
    value = value.strip()
    if not value:
        return '未知时间'
    if 'T' in value and len(value) >= 19:
        return f'{value[:19].replace("T", " ")} UTC'
    return value


def _build_github_update_html(records: tuple[GitHubUpdateRecord, ...]) -> str:
    cards: list[str] = []
    for index, record in enumerate(records):
        is_latest = index == 0
        card_class = 'record latest' if is_latest else 'record'
        badge = '最新' if is_latest else f'#{index + 1}'
        safe_message = html.escape(record.message)
        safe_author = html.escape(record.author)
        safe_time = html.escape(_format_github_update_time(record.updated_at))
        safe_sha = html.escape(record.sha or 'unknown')
        cards.append(
            f'''
            <div class="{card_class}">
              <div class="record-top">
                <span class="badge">{badge}</span>
                <span class="sha">{safe_sha}</span>
                <span class="time">{safe_time}</span>
              </div>
              <div class="message">{safe_message}</div>
              <div class="meta">by {safe_author}</div>
            </div>
            '''
        )

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {GITHUB_UPDATE_RENDER_WIDTH}px;
    padding: 40px;
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    color: #fff;
    background: linear-gradient(135deg, #2b1055 0%, #43275f 48%, #7c2d6b 100%);
  }}
  .wrap {{
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 28px;
    padding: 34px 36px 32px;
    background: rgba(20, 12, 38, 0.58);
    box-shadow: 0 22px 68px rgba(0,0,0,0.42);
  }}
  .header {{ display: flex; align-items: center; gap: 18px; }}
  .logo {{
    width: 70px; height: 70px; border-radius: 22px;
    display: flex; align-items: center; justify-content: center;
    font-size: 36px; background: linear-gradient(135deg, #ff7eb3, #ff758c);
    box-shadow: 0 8px 24px rgba(255,117,140,0.48);
  }}
  h1 {{ font-size: 30px; letter-spacing: 1px; }}
  .subtitle {{ margin-top: 7px; color: #c9b8e8; font-size: 14px; line-height: 1.55; }}
  .divider {{ height: 1px; margin: 26px 0 22px; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent); }}
  .list {{ display: grid; gap: 13px; }}
  .record {{
    border-radius: 18px; padding: 16px 18px;
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.09);
  }}
  .record.latest {{
    background: linear-gradient(135deg, rgba(255,126,179,0.22), rgba(182,155,255,0.15));
    border-color: rgba(255,126,179,0.48);
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06), 0 10px 28px rgba(255,117,140,0.16);
  }}
  .record-top {{ display: flex; align-items: center; gap: 10px; }}
  .badge {{
    padding: 4px 11px; border-radius: 999px; font-size: 12px; color: #ffe1ee;
    background: rgba(255,126,179,0.18); border: 1px solid rgba(255,126,179,0.32);
  }}
  .record.latest .badge {{ background: rgba(255,126,179,0.34); border-color: rgba(255,126,179,0.6); color: #fff; }}
  .sha {{ font-family: "Cascadia Code", "JetBrains Mono", monospace; color: #b69bff; font-size: 13px; }}
  .time {{ margin-left: auto; color: #9d8ec0; font-size: 12.5px; }}
  .message {{ margin-top: 12px; color: #fff; font-size: 17px; line-height: 1.55; font-weight: 700; word-break: break-word; }}
  .meta {{ margin-top: 10px; color: #c9b8e8; font-size: 12.5px; }}
  .footer {{ margin-top: 24px; text-align: center; color: #9d8ec0; font-size: 12px; }}
  .footer span {{ color: #ff9ecb; font-weight: 700; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <div class="logo">📝</div>
      <div>
        <h1>老婆更新记录</h1>
        <div class="subtitle">实时获取 GitHub 最近更新，按时间从新到旧排列</div>
      </div>
    </div>
    <div class="divider"></div>
    <div class="list">{''.join(cards)}</div>
    <div class="footer">TodayWaifu · GitHub 实时更新记录 · Created by <span>nnlmc</span></div>
  </div>
</body>
</html>'''


async def _render_github_update_image(records: tuple[GitHubUpdateRecord, ...]) -> Any:
    try:
        from gsuid_core.utils.html_render import render_html_to_bytes
    except Exception as exc:
        raise RuntimeError('当前 GSCore 未提供 HTML 渲染组件，请更新 GSCore 或安装 pyrenderhtml>=0.0.5。') from exc

    html_doc = _build_github_update_html(records)
    try:
        image = await render_html_to_bytes(
            html_doc,
            max_width=GITHUB_UPDATE_RENDER_WIDTH,
            dpi=96,
            default_font_size=14,
            font_name='sans-serif',
            image_format='png',
            lang='zh',
        )
    except Exception as exc:
        raise RuntimeError('老婆更新记录图片渲染失败，请查看控制台日志。') from exc

    try:
        from gsuid_core.utils.image.convert import convert_img

        return await convert_img(image)
    except Exception:
        return image


async def _send_github_update_log(bot: Bot, ev: Event) -> None:
    logger.info(f'{LOG_PREFIX} 用户 {ev.user_id} 请求老婆更新记录')
    if not _cfg_bool('DailyWifeUpdateLogEnabled', True):
        return await _send_prefixed(bot, '老婆更新记录功能当前已关闭。')

    try:
        records = await asyncio.to_thread(_github_update_fetch_sync)
        selected = _select_github_update_records(records)
        image = await _render_github_update_image(selected)
    except RuntimeError as exc:
        logger.warning(f'{LOG_PREFIX} 获取老婆更新记录失败: {exc}')
        return await _send_prefixed(bot, str(exc))

    await _send_prefixed(bot, MessageSegment.image(image))



@sv.on_fullmatch(('老婆更新记录', '今日老婆更新记录', '老婆更新日志'), block=True)
async def daily_wife_update_log(bot: Bot, ev: Event):
    await _send_github_update_log(bot, ev)


