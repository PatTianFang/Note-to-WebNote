import logging
import os

from .config import IMAGES_DIR, POSTS_BASE_DIR, WEBNOTE_ROOT
from .html_utils import refresh_common_page_chrome

def iter_site_html_pages():
    include_roots = [WEBNOTE_ROOT, IMAGES_DIR, POSTS_BASE_DIR]
    seen = set()
    for base_dir in include_roots:
        if not os.path.isdir(base_dir):
            continue
        for root, _dirs, files in os.walk(base_dir):
            for filename in files:
                if not filename.lower().endswith('.html'):
                    continue
                file_path = os.path.join(root, filename)
                abs_path = os.path.abspath(file_path)
                if abs_path in seen:
                    continue
                seen.add(abs_path)
                page_url = os.path.relpath(file_path, WEBNOTE_ROOT).replace(os.sep, '/')
                yield file_path, page_url

def sync_site_footers():
    ok = True
    updated_count = 0
    for file_path, page_url in iter_site_html_pages():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logging.warning(f"读取页面失败 [{file_path}]: {e}")
            ok = False
            continue

        updated = refresh_common_page_chrome(content, page_url)
        if updated == content:
            continue

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated)
            updated_count += 1
        except Exception as e:
            logging.warning(f"写入页面失败 [{file_path}]: {e}")
            ok = False

    logging.info(f"Footer 链接同步完成，共更新 {updated_count} 个页面")
    return ok
