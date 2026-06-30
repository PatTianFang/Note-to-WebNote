import json
import logging
import os
import re
from urllib.parse import unquote

from .config import IMAGES_DIR, POSTS_BASE_DIR, POSTS_JSON_PATH, RECORDS_JSON_PATH, WEBNOTE_ROOT
from .html_utils import clean_html_text, html_escape, refresh_css_href
from .paths import build_relative_url

PAGE_NAV_PATTERN = re.compile(
    r'\s*<!-- BEGIN PUBLISH PAGE NAV -->[\s\S]*?<!-- END PUBLISH PAGE NAV -->\s*',
    re.IGNORECASE,
)

def extract_html_metadata(html_content, fallback_title):
    clean_content = PAGE_NAV_PATTERN.sub('', html_content)
    scoped_content = clean_content
    article_match = re.search(r'<article[^>]*>([\s\S]*?)</article>', clean_content, re.IGNORECASE)
    main_match = re.search(r'<main[^>]*>([\s\S]*?)</main>', clean_content, re.IGNORECASE)
    if article_match:
        scoped_content = article_match.group(1)
    elif main_match:
        scoped_content = main_match.group(1)

    title = ''
    h1_match = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', scoped_content, re.IGNORECASE)
    if h1_match:
        title = clean_html_text(h1_match.group(1))

    if not title:
        title_match = re.search(r'<title[^>]*>([\s\S]*?)</title>', clean_content, re.IGNORECASE)
        if title_match:
            title = clean_html_text(title_match.group(1)).replace(" - FangTian's Note", '')

    excerpt = ''
    p_match = re.search(r'<p[^>]*>([\s\S]*?)</p>', scoped_content, re.IGNORECASE)
    if p_match:
        excerpt = clean_html_text(p_match.group(1))

    return {
        'title': title or fallback_title,
        'excerpt': excerpt[:140],
    }

def load_page_metadata():
    metadata = {}
    for json_path in (POSTS_JSON_PATH, RECORDS_JSON_PATH):
        if not os.path.exists(json_path):
            continue
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                items = json.load(f)
        except Exception as e:
            logging.warning(f"读取页面索引失败 [{json_path}]: {e}")
            continue

        for item in items:
            url = item.get('url', '').replace('\\', '/')
            if not url:
                continue
            metadata[url] = item
            metadata[unquote(url)] = item
    return metadata

def collect_html_pages(base_dir, metadata):
    pages = []
    if not os.path.isdir(base_dir):
        return pages

    for root, _dirs, files in os.walk(base_dir):
        for filename in files:
            if not filename.lower().endswith('.html'):
                continue

            file_path = os.path.join(root, filename)
            rel_url = os.path.relpath(file_path, WEBNOTE_ROOT).replace(os.sep, '/')
            meta = metadata.get(rel_url, {})
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception as e:
                logging.warning(f"读取 HTML 失败 [{file_path}]: {e}")
                continue

            fallback = extract_html_metadata(html_content, os.path.splitext(filename)[0])
            pages.append({
                'file_path': file_path,
                'url': rel_url,
                'title': meta.get('title') or fallback['title'],
                'date': meta.get('display_date') or meta.get('date') or '',
                'category': meta.get('category') or meta.get('place') or '',
                'excerpt': meta.get('excerpt') or fallback['excerpt'],
            })

    pages.sort(key=lambda item: (item.get('date') or '', item.get('title') or '', item.get('url') or ''))
    return pages

def build_page_nav_card(source_url, target, label):
    if not target:
        return f'''<span class="page-neighbor-card page-neighbor-card-disabled">
                    <span class="page-neighbor-label">{label}</span>
                    <strong>没有更多内容</strong>
                </span>'''

    href = build_relative_url(source_url, target['url'])
    meta_parts = [target.get('date', ''), target.get('category', '')]
    meta_text = ' · '.join(part for part in meta_parts if part)
    excerpt = target.get('excerpt', '')

    return f'''<a class="page-neighbor-card" href="{html_escape(href)}">
                    <span class="page-neighbor-label">{label}</span>
                    <strong>{html_escape(target.get('title') or '未命名页面')}</strong>
                    {f'<span class="page-neighbor-meta">{html_escape(meta_text)}</span>' if meta_text else ''}
                    {f'<p>{html_escape(excerpt)}</p>' if excerpt else ''}
                </a>'''

def build_page_navigation_html(source_url, prev_page, next_page):
    return f'''
<!-- BEGIN PUBLISH PAGE NAV -->
<nav class="page-neighbor-nav" aria-label="上一篇和下一篇">
    {build_page_nav_card(source_url, prev_page, '上一篇')}
    {build_page_nav_card(source_url, next_page, '下一篇')}
</nav>
<!-- END PUBLISH PAGE NAV -->
'''

def inject_page_navigation(file_path, page_url, nav_html):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logging.warning(f"读取页面失败 [{file_path}]: {e}")
        return False

    content = PAGE_NAV_PATTERN.sub('\n', content)
    insert_match = list(re.finditer(r'</article>', content, re.IGNORECASE))
    if insert_match:
        match = insert_match[-1]
        content = content[:match.start()] + nav_html + content[match.start():]
    else:
        match = re.search(r'</main>', content, re.IGNORECASE)
        if not match:
            logging.warning(f"未找到可插入导航的位置: {file_path}")
            return False
        content = content[:match.start()] + nav_html + content[match.start():]

    content = refresh_css_href(content, page_url)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return True

def sync_page_navigation():
    metadata = load_page_metadata()
    page_groups = [
        collect_html_pages(IMAGES_DIR, metadata),
        collect_html_pages(POSTS_BASE_DIR, metadata),
    ]

    ok = True
    injected_count = 0
    for pages in page_groups:
        for index, page in enumerate(pages):
            prev_page = pages[index - 1] if index > 0 else None
            next_page = pages[index + 1] if index + 1 < len(pages) else None
            nav_html = build_page_navigation_html(page['url'], prev_page, next_page)
            if inject_page_navigation(page['file_path'], page['url'], nav_html):
                injected_count += 1
            else:
                ok = False

    logging.info(f"页面上一篇/下一篇导航更新完成，共 {injected_count} 个页面")
    return ok
