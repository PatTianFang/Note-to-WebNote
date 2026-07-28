import json
import logging
import shutil
from pathlib import Path

from .config import IMAGE_EXTENSIONS, NOTE_ROOT, SOURCE_COPY_CONFIG_PATH


COPY_EXTENSIONS = IMAGE_EXTENSIONS | {'.md', '.pdf'}


def _resolve_destination(note_root, destination):
    destination = Path(destination)
    if destination.is_absolute():
        raise ValueError('destination 必须是 Note 目录下的相对路径')

    note_root = Path(note_root).resolve()
    target = (note_root / destination).resolve()
    if target != note_root and note_root not in target.parents:
        raise ValueError('destination 不能指向 Note 目录之外')
    return target


def _load_copy_entries(config_path):
    config_path = Path(config_path)
    with config_path.open('r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    entries = config.get('copies') if isinstance(config, dict) else None
    if not isinstance(entries, list):
        raise ValueError('配置必须包含 copies 数组')
    return entries


def _copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        source_stat = source.stat()
        target_stat = target.stat()
        if source_stat.st_size == target_stat.st_size and source_stat.st_mtime_ns == target_stat.st_mtime_ns:
            return False
    shutil.copy2(source, target)
    return True


def _copy_allowed_files(source, target):
    matched = 0
    copied = 0
    files = source.rglob('*') if source.is_dir() else [source]
    for source_file in files:
        if not source_file.is_file() or source_file.suffix.lower() not in COPY_EXTENSIONS:
            continue
        matched += 1
        relative_path = source_file.relative_to(source) if source.is_dir() else Path(source_file.name)
        copied += _copy_file(source_file, target / relative_path)
    return matched, copied


def copy_configured_sources(config_path=SOURCE_COPY_CONFIG_PATH, note_root=NOTE_ROOT):
    config_path = Path(config_path)
    try:
        entries = _load_copy_entries(config_path)
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict) or not isinstance(entry.get('source'), str) or not isinstance(entry.get('destination'), str):
                raise ValueError(f'copies[{index}] 必须包含字符串 source 和 destination')

            source = Path(entry['source']).expanduser()
            if not source.is_absolute():
                source = config_path.parent / source
            source = source.resolve()
            if not source.exists():
                raise FileNotFoundError(f'源路径不存在: {source}')

            target = _resolve_destination(note_root, entry['destination'])
            if not source.is_dir() and not source.is_file():
                raise ValueError(f'源路径不是普通文件或目录: {source}')
            matched, copied = _copy_allowed_files(source, target)
            logging.info('已同步 %s 到 %s：匹配 %d 个文件，更新 %d 个', source, target, matched, copied)
        return True
    except (OSError, ValueError, json.JSONDecodeError) as error:
        logging.error('复制配置源文件失败: %s', error)
        return False
