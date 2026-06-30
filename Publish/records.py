import json
import logging
import os
import re
import shutil
from datetime import datetime

from .config import (
    GENERATED_BY,
    IMAGE_EXTENSIONS,
    IMAGES_DIR,
    RECORDS_DATA_JS_PATH,
    RECORDS_JSON_PATH,
    RECORDS_SOURCE_DIR,
    RECORD_PLACE_COORDS,
    WEBNOTE_ROOT,
)
from .html_utils import html_escape, build_footer_html
from .paths import build_css_href_for_url, url_path_join
from .r2 import build_public_r2_url, build_record_image_object_key, prune_r2_manifest, upload_image_to_r2, get_r2_config
from .manifest import load_r2_manifest, save_r2_manifest
from .cleanup import remove_path_if_exists
from .posts_index import delete_file_if_exists

def parse_record_name(record_name):
    match = re.match(r'^(\d{8})(.*)$', record_name)
    if not match:
        return {
            'place': record_name,
            'display_date': '',
            'iso_date': '',
        }

    date_part, place = match.groups()
    try:
        dt = datetime.strptime(date_part, '%Y%m%d')
    except ValueError:
        return {
            'place': place or record_name,
            'display_date': '',
            'iso_date': '',
        }

    return {
        'place': place or record_name,
        'display_date': f'{dt.year}年{dt.month:02d}月{dt.day:02d}日',
        'iso_date': dt.strftime('%Y-%m-%d'),
    }

def get_record_coords(place):
    return RECORD_PLACE_COORDS.get(place)

def is_image_file(filename):
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS

def copy_record_assets(record_dir, target_asset_dir):
    os.makedirs(target_asset_dir, exist_ok=True)
    copied_images = []

    for filename in sorted(os.listdir(record_dir)):
        source_file = os.path.join(record_dir, filename)
        if not os.path.isfile(source_file) or not is_image_file(filename):
            continue

        target_file = os.path.join(target_asset_dir, filename)
        shutil.copy2(source_file, target_file)
        copied_images.append(filename)

    return copied_images

def convert_record_markdown_to_html(markdown_text, record_name, image_filenames, image_urls=None):
    image_names = set(image_filenames)
    image_urls = image_urls or {}
    referenced_images = []

    def replace_image(match):
        image_name = match.group(1).strip()
        if image_name in image_names:
            referenced_images.append(image_name)
            src = image_urls.get(image_name) or url_path_join(record_name, image_name)
            alt = os.path.splitext(image_name)[0]
            return f'\n<figure class="record-auto-photo"><img src="{html_escape(src)}" alt="{html_escape(alt)}"></figure>\n'
        return html_escape(match.group(0))

    converted = re.sub(r'!\[\[([^\]]+)\]\]', replace_image, markdown_text)
    lines = converted.splitlines()
    blocks = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith('<figure '):
            blocks.append(stripped)
            continue

        if stripped.startswith('# '):
            blocks.append(f'<h2>{html_escape(stripped[2:].strip())}</h2>')
            continue

        blocks.append(f'<p>{html_escape(stripped)}</p>')

    for image_name in image_filenames:
        if image_name in referenced_images:
            continue
        src = image_urls.get(image_name) or url_path_join(record_name, image_name)
        alt = os.path.splitext(image_name)[0]
        blocks.append(f'<figure class="record-auto-photo"><img src="{html_escape(src)}" alt="{html_escape(alt)}"></figure>')

    return '\n'.join(blocks), referenced_images

def split_record_body(body_html):
    image_blocks = []

    def collect_image(match):
        image_blocks.append(match.group(0))
        return ''

    text_html = re.sub(
        r'\s*<figure class="record-auto-photo">[\s\S]*?</figure>\s*',
        collect_image,
        body_html,
    ).strip()

    return text_html, image_blocks

def get_record_markdown(record_dir, record_name):
    preferred_path = os.path.join(record_dir, f'{record_name}.md')
    if os.path.isfile(preferred_path):
        return preferred_path

    markdown_files = [
        os.path.join(record_dir, filename)
        for filename in sorted(os.listdir(record_dir))
        if filename.lower().endswith('.md') and os.path.isfile(os.path.join(record_dir, filename))
    ]
    return markdown_files[0] if markdown_files else None

def build_record_page(record_name, record_info, body_html, image_count):
    title = html_escape(record_name)
    text_html, image_blocks = split_record_body(body_html)
    intro_html = text_html or '<p>保持热爱，奔赴山海。</p>'
    gallery_html = '\n'.join(image_blocks) if image_blocks else '<p class="empty-message">暂无图片。</p>'
    display_date = record_info.get('display_date') or ''
    place = record_info.get('place') or record_name
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - FangTian's Note</title>
    <link rel="stylesheet" href="{html_escape(build_css_href_for_url(f'images/{record_name}.html'))}">
    <script src="../js/theme.js"></script>
</head>
<body>
    <header>
        <div class="container header-container">
            <h1><a href="../index.html">FangTian's Note</a></h1>
            <nav>
                <a href="../index.html">首页</a>
                <a href="../records.html">记录</a>
                <a href="../about.html">关于</a>
            </nav>
        </div>
    </header>

    <main class="record-auto-page">
        <article class="record-auto-layout">
            <header class="record-auto-header">
                <p class="records-kicker">Record</p>
                <h1>{title}</h1>
                <div class="post-meta">
                    <span>{html_escape(display_date)}</span>
                    <span class="post-category">记录</span>
                </div>
            </header>

            <section class="record-auto-summary" aria-label="记录信息">
                <div class="record-auto-intro">
                    {intro_html}
                </div>
                <div class="record-facts">
                    <div>
                        <span>拍摄地点</span>
                        <strong>{html_escape(place)}</strong>
                    </div>
                    <div>
                        <span>图片</span>
                        <strong>{image_count} 张</strong>
                    </div>
                    <div>
                        <span>时间</span>
                        <strong>{html_escape(display_date or '未知')}</strong>
                    </div>
                </div>
            </section>

            <section class="record-auto-gallery" aria-label="照片">
                {gallery_html}
            </section>
            <div class="record-lightbox" aria-hidden="true">
                <button class="record-lightbox-close" type="button" aria-label="关闭">×</button>
                <button class="record-lightbox-nav record-lightbox-prev" type="button" aria-label="上一张">‹</button>
                <img class="record-lightbox-image" src="" alt="">
                <button class="record-lightbox-nav record-lightbox-next" type="button" aria-label="下一张">›</button>
                <div class="record-lightbox-toolbar">
                    <span class="record-lightbox-count"></span>
                    <a class="record-lightbox-download" href="" download>下载照片</a>
                </div>
            </div>
        </article>
    </main>

    {build_footer_html(f'images/{record_name}.html')}
    <script>
    (function () {{
        const images = Array.from(document.querySelectorAll('.record-auto-photo img'));
        const lightbox = document.querySelector('.record-lightbox');
        if (!images.length || !lightbox) return;

        const imageEl = lightbox.querySelector('.record-lightbox-image');
        const closeBtn = lightbox.querySelector('.record-lightbox-close');
        const prevBtn = lightbox.querySelector('.record-lightbox-prev');
        const nextBtn = lightbox.querySelector('.record-lightbox-next');
        const countEl = lightbox.querySelector('.record-lightbox-count');
        const downloadEl = lightbox.querySelector('.record-lightbox-download');
        let activeIndex = 0;

        function show(index) {{
            activeIndex = (index + images.length) % images.length;
            const source = images[activeIndex];
            const src = source.currentSrc || source.src;
            imageEl.src = src;
            imageEl.alt = source.alt || '';
            countEl.textContent = `${{activeIndex + 1}} / ${{images.length}}`;
            downloadEl.href = src;
            downloadEl.download = source.alt || 'record-photo';
        }}

        function open(index) {{
            show(index);
            lightbox.setAttribute('aria-hidden', 'false');
            document.body.classList.add('record-lightbox-open');
            closeBtn.focus();
        }}

        function close() {{
            lightbox.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('record-lightbox-open');
            imageEl.removeAttribute('src');
        }}

        images.forEach((image, index) => {{
            image.addEventListener('click', () => open(index));
            image.setAttribute('tabindex', '0');
            image.addEventListener('keydown', event => {{
                if (event.key === 'Enter' || event.key === ' ') {{
                    event.preventDefault();
                    open(index);
                }}
            }});
        }});

        closeBtn.addEventListener('click', close);
        prevBtn.addEventListener('click', () => show(activeIndex - 1));
        nextBtn.addEventListener('click', () => show(activeIndex + 1));
        lightbox.addEventListener('click', event => {{
            if (event.target === lightbox) close();
        }});
        document.addEventListener('keydown', event => {{
            if (lightbox.getAttribute('aria-hidden') === 'true') return;
            if (event.key === 'Escape') close();
            if (event.key === 'ArrowLeft') show(activeIndex - 1);
            if (event.key === 'ArrowRight') show(activeIndex + 1);
        }});
    }}());
    </script>
</body>
</html>
'''

def cleanup_stale_record_pages(current_urls):
    if not os.path.exists(RECORDS_JSON_PATH):
        return True

    ok = True
    try:
        with open(RECORDS_JSON_PATH, 'r', encoding='utf-8') as f:
            existing_records = json.load(f)
    except Exception as e:
        logging.warning(f"读取 records.json 失败，跳过旧记录清理: {e}")
        return False

    for record in existing_records:
        if record.get('generated_by') != GENERATED_BY:
            continue

        record_url = record.get('url', '')
        if not record_url or record_url in current_urls:
            continue

        record_id = record.get('id', '')
        html_path = os.path.join(WEBNOTE_ROOT, *record_url.split('/'))
        asset_dir = os.path.join(IMAGES_DIR, record_id) if record_id else ''

        delete_file_if_exists(html_path)
        if asset_dir and os.path.isdir(asset_dir):
            ok = remove_path_if_exists(asset_dir) and ok

    return ok

def sync_record_pages():
    if not os.path.isdir(RECORDS_SOURCE_DIR):
        logging.info(f"记录目录不存在，跳过记录页生成: {RECORDS_SOURCE_DIR}")
        return True

    r2_config = get_r2_config()
    if not r2_config:
        return False

    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(RECORDS_JSON_PATH), exist_ok=True)
    r2_manifest = load_r2_manifest()
    records = []
    current_urls = set()
    current_image_object_keys = set()
    had_errors = False

    for record_name in sorted(os.listdir(RECORDS_SOURCE_DIR)):
        record_dir = os.path.join(RECORDS_SOURCE_DIR, record_name)
        if not os.path.isdir(record_dir):
            continue

        try:
            target_asset_dir = os.path.join(IMAGES_DIR, record_name)
            image_filenames = copy_record_assets(record_dir, target_asset_dir)
            image_urls = {}
            for image_name in image_filenames:
                source_image = os.path.join(record_dir, image_name)
                object_key = build_record_image_object_key(record_name, image_name)
                current_image_object_keys.add(object_key)
                if not upload_image_to_r2(r2_config, source_image, object_key, r2_manifest):
                    had_errors = True
                    break

                image_version = int(os.path.getmtime(source_image))
                image_urls[image_name] = build_public_r2_url(
                    r2_config['public_base_url'],
                    object_key,
                    image_version,
                )

            if had_errors:
                continue

            markdown_path = get_record_markdown(record_dir, record_name)
            markdown_text = ''
            if markdown_path:
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()

            body_html, _referenced_images = convert_record_markdown_to_html(
                markdown_text,
                record_name,
                image_filenames,
                image_urls,
            )
            if not body_html:
                body_html = '<p>暂无文字记录。</p>'

            st = os.stat(markdown_path or record_dir)
            record_info = parse_record_name(record_name)
            create_time_str = record_info.get('iso_date') or datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d')
            display_date = record_info.get('display_date') or create_time_str
            target_html_file = os.path.join(IMAGES_DIR, f'{record_name}.html')
            with open(target_html_file, 'w', encoding='utf-8') as f:
                f.write(build_record_page(record_name, record_info, body_html, len(image_filenames)))

            first_image = image_filenames[0] if image_filenames else ''
            record_place = record_info.get('place') or record_name
            records.append({
                'id': record_name,
                'title': record_name,
                'date': create_time_str,
                'display_date': display_date,
                'place': record_place,
                'coords': get_record_coords(record_place),
                'url': url_path_join('images', f'{record_name}.html'),
                'excerpt': f'{display_date}，拍摄地点：{record_place}，共 {len(image_filenames)} 张图片。',
                'cover': image_urls.get(first_image, '') if first_image else '',
                'generated_by': GENERATED_BY,
            })
            current_urls.add(records[-1]['url'])
            logging.info(f"记录页生成成功: {target_html_file}")
        except Exception as e:
            logging.error(f"处理记录文件夹失败 [{record_name}]: {e}")
            return False

    if had_errors:
        save_r2_manifest(r2_manifest)
        logging.error("存在记录图片上传失败，已跳过 records.json 更新以保护现有索引")
        return False

    if not cleanup_stale_record_pages(current_urls):
        save_r2_manifest(r2_manifest)
        return False

    records.sort(key=lambda item: item.get('date', ''), reverse=True)
    with open(RECORDS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=4)
    with open(RECORDS_DATA_JS_PATH, 'w', encoding='utf-8') as f:
        f.write('window.WEBNOTE_RECORDS = ')
        json.dump(records, f, ensure_ascii=False, indent=4)
        f.write(';\n')
    prune_r2_manifest(r2_manifest, current_image_object_keys, r2_config, prefixes=['images/'])
    save_r2_manifest(r2_manifest)
    logging.info(f"更新 records.json 成功，共 {len(records)} 条记录")
    return True
