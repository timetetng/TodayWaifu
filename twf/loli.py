"""TodayWaifu - loli module."""
from __future__ import annotations

from .shared import *  # noqa: F403


def _safe_loli_image_name(filename: str, index: int) -> str:
    suffix = Path(filename).suffix.lower()
    stem = re.sub(r'[^0-9A-Za-z._-]+', '_', Path(filename).stem).strip('._-')
    if not stem:
        stem = f'image_{index}'
    return f'{stem}{suffix}'


def _unique_loli_image_path(root: Path, filename: str) -> Path:
    suffix = Path(filename).suffix.lower()
    stem = Path(filename).stem
    candidate = root / filename
    counter = 1
    while candidate.exists():
        candidate = root / f'{stem}_{counter}{suffix}'
        counter += 1
    return candidate


def _loli_image_paths() -> tuple[Path, ...]:
    root = _loli_image_root()
    if not root.is_dir():
        return ()
    images = [
        path
        for path in root.rglob('*')
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return tuple(sorted(images, key=lambda path: str(path).lower()))


def _probe_url_ok(url: str, timeout: int) -> bool:
    """快速测速：用 1 字节 Range 请求，timeout 内成功响应即视为可用。"""
    if not url:
        return False
    request = Request(url, headers={'User-Agent': 'TodayWaifu/1.0', 'Range': 'bytes=0-0'})
    try:
        with urlopen(request, timeout=timeout) as response:
            code = getattr(response, 'status', 200)
            response.read(1)
            return 200 <= code < 400
    except Exception as exc:  # noqa: BLE001
        logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 测速下载源失败: {exc}')
        return False


def _select_loli_download_source() -> tuple[str, bool]:
    """选择下载源：优先测速直连 GitHub，慢/失败则切备用源。

    返回 (下载地址, 是否走备用源)。
    """
    logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 开始测速直连 GitHub 下载源')
    if _probe_url_ok(LOLI_IMAGE_REPO_ZIP_URL, LOLI_DOWNLOAD_PROBE_TIMEOUT):
        logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 直连 GitHub 测速正常，使用直连下载源')
        return LOLI_IMAGE_REPO_ZIP_URL, False
    if LOLI_IMAGE_BACKUP_ZIP_URL:
        logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 直连 GitHub 测速偏慢/失败，改用备用下载源')
        return LOLI_IMAGE_BACKUP_ZIP_URL, True
    logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 未配置备用下载源，仍使用直连下载源')
    return LOLI_IMAGE_REPO_ZIP_URL, False


def _human_size(num: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num < 1024 or unit == 'GB':
            return f'{num:.1f}{unit}' if unit != 'B' else f'{int(num)}B'
        num /= 1024
    return f'{num:.1f}GB'


def _download_loli_zip(zip_path: Path, url: str, *, source_label: str = '') -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    label = f'（{source_label}）' if source_label else ''
    logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 开始下载压缩包{label} url={url}')
    request = Request(url, headers={'User-Agent': 'TodayWaifu/1.0'})
    try:
        with urlopen(request, timeout=60) as response:
            content_length = 0
            try:
                content_length = int(response.headers.get('Content-Length') or 0)
            except (TypeError, ValueError):
                content_length = 0
            size_hint = _human_size(content_length) if content_length else '未知'
            logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 已连接下载源，文件大小：{size_hint}')

            total = 0
            next_log_at = 8 * 1024 * 1024  # 每约 8MB 打一次进度
            start_ts = time.time()
            with zip_path.open('wb') as file:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > LOLI_IMAGE_ZIP_MAX_BYTES:
                        raise RuntimeError('下载到的图片压缩包过大。')
                    file.write(chunk)
                    if total >= next_log_at:
                        if content_length:
                            pct = total * 100 / content_length
                            logger.info(
                                f'{LOLI_DOWNLOAD_LOG_PREFIX} 下载进度 {pct:.0f}% '
                                f'（{_human_size(total)}/{_human_size(content_length)}）'
                            )
                        else:
                            logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 下载进度 {_human_size(total)}')
                        next_log_at += 8 * 1024 * 1024
    except HTTPError as exc:
        raise RuntimeError(f'下载萝莉图片失败，HTTP {exc.code}。') from exc
    except URLError as exc:
        raise RuntimeError(f'下载萝莉图片失败：{exc.reason}') from exc
    except TimeoutError as exc:
        raise RuntimeError('下载萝莉图片超时。') from exc

    if not zip_path.is_file() or zip_path.stat().st_size <= 0:
        raise RuntimeError('下载到的图片压缩包为空。')
    if not zipfile.is_zipfile(zip_path):
        raise RuntimeError('下载到的文件不是有效 zip 压缩包。')
    elapsed = max(0.001, time.time() - start_ts)
    logger.info(
        f'{LOLI_DOWNLOAD_LOG_PREFIX} 压缩包下载完成，共 {_human_size(zip_path.stat().st_size)}，'
        f'耗时 {elapsed:.1f}s，均速 {_human_size(total / elapsed)}/s'
    )


def _existing_loli_image_hashes() -> set[str]:
    hashes: set[str] = set()
    for path in _loli_image_paths():
        try:
            hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
        except OSError as exc:
            logger.warning(f'{LOG_PREFIX} 读取萝莉图片用于查重失败: {path} -> {exc}')
    return hashes


def _extract_loli_images(zip_path: Path) -> LoliImageDownloadResult:
    target_root = _loli_image_root()
    target_root.mkdir(parents=True, exist_ok=True)
    logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 开始解压并查重，目标目录：{target_root}')
    existing_hashes = _existing_loli_image_hashes()
    logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 已有图片 {len(existing_hashes)} 张用于查重')

    saved = 0
    duplicated = 0
    skipped = 0
    total_size = 0
    processed = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            entries = archive.infolist()
            total_entries = sum(1 for info in entries if not info.is_dir())
            logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 压缩包内共 {total_entries} 个文件，开始逐个处理')
            for index, info in enumerate(entries, 1):
                if info.is_dir():
                    continue
                processed += 1
                filename = Path(info.filename.replace('\\', '/')).name
                suffix = Path(filename).suffix.lower()
                if suffix not in IMAGE_EXTENSIONS:
                    skipped += 1
                    continue
                if info.file_size <= 0 or info.file_size > UPLOAD_IMAGE_MAX_BYTES:
                    skipped += 1
                    continue
                total_size += info.file_size
                if total_size > LOLI_IMAGE_ZIP_MAX_BYTES:
                    raise RuntimeError('图片压缩包解压后体积过大。')
                with archive.open(info) as source:
                    data = source.read(UPLOAD_IMAGE_MAX_BYTES + 1)
                if not data or len(data) > UPLOAD_IMAGE_MAX_BYTES:
                    skipped += 1
                    continue
                image_hash = hashlib.sha256(data).hexdigest()
                if image_hash in existing_hashes:
                    duplicated += 1
                    continue
                image_name = _safe_loli_image_name(filename, index)
                image_path = _unique_loli_image_path(target_root, image_name)
                image_path.write_bytes(data)
                existing_hashes.add(image_hash)
                saved += 1
                if saved % 50 == 0:
                    logger.info(
                        f'{LOLI_DOWNLOAD_LOG_PREFIX} 解压进度：已处理 {processed}/{total_entries}，'
                        f'新增 {saved} 张'
                    )
    except zipfile.BadZipFile as exc:
        raise RuntimeError('图片压缩包解压失败。') from exc

    if saved <= 0 and duplicated <= 0:
        raise RuntimeError('图片压缩包里没有找到可用图片。')
    logger.info(
        f'{LOLI_DOWNLOAD_LOG_PREFIX} 解压完成：新增 {saved} 张，重复跳过 {duplicated} 张，'
        f'无效跳过 {skipped} 个，累计解压 {_human_size(total_size)}'
    )
    return LoliImageDownloadResult(saved=saved, duplicated=duplicated, skipped=skipped)


def _download_and_extract_loli_images(url: str, *, source_label: str = '') -> LoliImageDownloadResult:
    zip_path = _custom_upload_data_root() / f'loli_images.{int(time.time() * 1000)}.zip.tmp'
    logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 临时压缩包路径：{zip_path}')
    try:
        _download_loli_zip(zip_path, url, source_label=source_label)
        return _extract_loli_images(zip_path)
    finally:
        if zip_path.exists():
            zip_path.unlink()
            logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 已清理临时压缩包')


def _delete_loli_images() -> int:
    root = _loli_image_root()
    count = len(_loli_image_paths())
    if root.exists():
        if root.is_dir():
            shutil.rmtree(root)
        else:
            root.unlink()
    return count



async def _send_loli_image(bot: Bot, ev: Event) -> None:
    images = _loli_image_paths()
    if not images:
        return await _send_loli_text(bot, '还没有萝莉图片，请先发送“下载萝莉图片”。')

    image = random.choice(images)
    logger.info(f'{LOG_PREFIX} 用户 {ev.user_id} 请求今日萝莉，发送图片: {image}')
    await bot.send([
        _with_loli_reply_prefix('你今天的萝莉是'),
        MessageSegment.image(image),
    ])


async def _send_download_loli_images(bot: Bot, ev: Event) -> None:
    logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 用户 {ev.user_id} 触发下载萝莉图片命令')
    await _send_loli_text(bot, '正在测速选择下载线路，请稍等...')

    url, use_backup = await asyncio.to_thread(_select_loli_download_source)
    if use_backup:
        logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 直连 GitHub 较慢，切换备用下载源')
        await _send_loli_text(bot, '直连 GitHub 较慢，已切换备用下载源，开始下载...')
    else:
        logger.info(f'{LOLI_DOWNLOAD_LOG_PREFIX} 直连 GitHub 正常，使用直连下载')
        await _send_loli_text(bot, '直连 GitHub 正常，开始下载...')

    source_label = '备用下载源' if use_backup else '直连 GitHub'
    try:
        result = await asyncio.to_thread(_download_and_extract_loli_images, url, source_label=source_label)
    except RuntimeError as exc:
        # 直连失败时再兜底尝试一次备用源
        if not use_backup and LOLI_IMAGE_BACKUP_ZIP_URL:
            logger.warning(f'{LOLI_DOWNLOAD_LOG_PREFIX} 直连下载失败({exc})，改用备用下载源重试')
            await _send_loli_text(bot, '直连下载失败，正在改用备用下载源重试...')
            try:
                result = await asyncio.to_thread(
                    _download_and_extract_loli_images, LOLI_IMAGE_BACKUP_ZIP_URL, source_label='备用下载源'
                )
            except RuntimeError as exc2:
                logger.warning(f'{LOLI_DOWNLOAD_LOG_PREFIX} 备用下载源也失败: {exc2}')
                return await _send_loli_text(bot, str(exc2))
        else:
            logger.warning(f'{LOLI_DOWNLOAD_LOG_PREFIX} 下载萝莉图片失败: {exc}')
            return await _send_loli_text(bot, str(exc))

    logger.info(
        f'{LOLI_DOWNLOAD_LOG_PREFIX} 下载完成 新增={result.saved} 重复={result.duplicated} 无效={result.skipped}'
    )
    await _send_loli_text(
        bot,
        f'萝莉图片下载完成\n新增：{result.saved} 张\n重复跳过：{result.duplicated} 张\n无效跳过：{result.skipped} 个',
    )


async def _send_delete_loli_images(bot: Bot, ev: Event) -> None:
    logger.info(f'{LOG_PREFIX} 用户 {ev.user_id} 触发删除萝莉图片命令')
    count = await asyncio.to_thread(_delete_loli_images)
    await _send_loli_text(bot, f'已删除全部萝莉图片，共 {count} 张。')



@upload_sv.on_fullmatch('下载萝莉图片', block=True)
async def download_loli_images(bot: Bot, ev: Event):
    await _send_download_loli_images(bot, ev)


@upload_sv.on_fullmatch('删除萝莉图片', block=True)
async def delete_loli_images(bot: Bot, ev: Event):
    await _send_delete_loli_images(bot, ev)



@sv.on_fullmatch('今日萝莉', block=True)
async def daily_loli(bot: Bot, ev: Event):
    await _send_loli_image(bot, ev)


@sv.on_fullmatch('今日正太', block=True)
async def daily_shota(bot: Bot, ev: Event):
    logger.info(f'{LOG_PREFIX} 用户 {ev.user_id} 触发今日正太命令')
    await _send_shota_text(bot, '今日正太功能正在完善，敬请期待~')


@sv.on_fullmatch('今日御姐', block=True)
async def daily_yujie(bot: Bot, ev: Event):
    logger.info(f'{LOG_PREFIX} 用户 {ev.user_id} 触发今日御姐命令')
    await _send_yujie_text(bot, '今日御姐功能正在完善，敬请期待~')


