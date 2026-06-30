import logging
import os
from datetime import datetime

from .config import HTML_TEMPLATE_PATH, POSTS_BASE_DIR, WEBNOTE_ROOT
from .cleanup import cleanup_empty_directories
from .html_utils import html_escape, refresh_footer
from .manifest import load_r2_manifest, save_r2_manifest
from .paths import build_css_href_for_url
from .posts_index import build_post_entry, update_posts_json
from .r2 import build_public_pdf_url, build_r2_object_key_from_source, get_r2_config, prune_r2_manifest, upload_pdf_to_r2

def get_html_template():
    try:
        with open(HTML_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"读取 HTML 模板失败: {e}")
        return ""

def build_post_url_from_source(source_file, source_base_dir):
    rel_path = os.path.relpath(source_file, source_base_dir)
    rel_html_path = f"{os.path.splitext(rel_path)[0]}.html"
    return f"posts/{rel_html_path.replace(os.sep, '/')}"

def build_site_root_prefix(post_url):
    directory = os.path.dirname(post_url.replace('/', os.sep))
    depth = len([part for part in directory.split(os.sep) if part])
    return '../' * depth

def build_pdf_viewer_html(pdf_url, root_prefix):
    return f'''<section class="pdf-viewer" data-pdf-viewer data-pdf-url="{html_escape(pdf_url)}" data-root-prefix="{html_escape(root_prefix)}">
                        <div class="pdf-viewer-toolbar">
                            <div class="pdf-viewer-pages">
                                <button type="button" data-pdf-mode-list>纵向列表</button>
                                <button type="button" data-pdf-mode-single>单页翻页</button>
                                <span><span data-pdf-current>--</span> / <span data-pdf-total>--</span></span>
                            </div>
                            <div class="pdf-viewer-actions">
                                <button type="button" data-pdf-prev>上一页</button>
                                <button type="button" data-pdf-next>下一页</button>
                                <button type="button" data-pdf-zoom-out>缩小</button>
                                <button type="button" data-pdf-zoom-in>放大</button>
                                <a href="{html_escape(pdf_url)}" target="_blank" rel="noopener">打开 PDF</a>
                                <a href="{html_escape(pdf_url)}" download>下载 PDF</a>
                            </div>
                        </div>
                        <div class="pdf-viewer-stage">
                            <div class="pdf-viewer-pages-list" data-pdf-pages></div>
                            <div class="pdf-viewer-single" data-pdf-single hidden>
                                <canvas data-pdf-canvas></canvas>
                            </div>
                            <p class="pdf-viewer-status" data-pdf-status>正在加载 PDF...</p>
                        </div>
                    </section>'''

def sync_pdf_files():
    source_base_dir = os.path.join('.', 'Note')

    if not os.path.exists(source_base_dir):
        logging.error(f"源目录不存在: {source_base_dir}")
        return False

    r2_config = get_r2_config()
    if not r2_config:
        return False

    html_template = get_html_template()
    if not html_template:
        return False

    r2_manifest = load_r2_manifest()
    current_posts_by_url = {}
    current_object_keys = set()
    had_errors = False

    try:
        items = os.listdir(source_base_dir)
    except Exception as e:
        logging.error(f"无法读取源目录: {e}")
        return False

    for item in items:
        source_category_dir = os.path.join(source_base_dir, item)
        if not os.path.isdir(source_category_dir):
            continue

        target_posts_dir = os.path.join(POSTS_BASE_DIR, item)

        try:
            os.makedirs(target_posts_dir, exist_ok=True)
        except Exception as e:
            logging.error(f"创建目标文件夹失败 [{target_posts_dir}]: {e}")
            continue

        for root, _dirs, files in os.walk(source_category_dir):
            for filename in files:
                if not filename.lower().endswith('.pdf'):
                    continue

                source_file = os.path.join(root, filename)
                pdf_name_no_ext = os.path.splitext(filename)[0]
                post_url = build_post_url_from_source(source_file, source_base_dir)
                target_html_file = os.path.join(WEBNOTE_ROOT, *post_url.split('/'))

                try:
                    os.makedirs(os.path.dirname(target_html_file), exist_ok=True)
                    st = os.stat(source_file)
                    create_time_str = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d')
                    object_key = build_r2_object_key_from_source(source_file, source_base_dir)
                    current_object_keys.add(object_key)
                    pdf_version = int(st.st_mtime)
                    pdf_url = build_public_pdf_url(r2_config['public_base_url'], object_key, pdf_version)

                    if not upload_pdf_to_r2(r2_config, source_file, object_key, r2_manifest):
                        had_errors = True
                        continue
                    logging.info(f"PDF 上传 R2 成功: {object_key}")

                    content = html_template
                    site_root_prefix = build_site_root_prefix(post_url)
                    embed_tag = build_pdf_viewer_html(pdf_url, site_root_prefix)
                    content = content.replace('模板修改1', pdf_name_no_ext)
                    content = content.replace('模板修改2', create_time_str)
                    content = content.replace('模板修改3', item)
                    content = content.replace('模板修改4', f'关于 {pdf_name_no_ext} 的详细内容。')
                    content = content.replace('模板修改5', embed_tag)
                    content = content.replace('模板修改6', pdf_url)

                    content = content.replace('../../css/style.css', build_css_href_for_url(post_url))
                    content = content.replace('../../js/theme.js', f'{site_root_prefix}js/theme.js')
                    content = content.replace('../../js/pdf-viewer.js', f'{site_root_prefix}js/pdf-viewer.js')
                    content = content.replace('../../index.html', f'{site_root_prefix}index.html')
                    content = content.replace('../../records.html', f'{site_root_prefix}records.html')
                    content = content.replace('../../about.html', f'{site_root_prefix}about.html')
                    content = refresh_footer(content, post_url)

                    with open(target_html_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logging.info(f"HTML 创建成功: {pdf_name_no_ext}.html")

                    post_entry = build_post_entry(pdf_name_no_ext, item, create_time_str, post_url, object_key)
                    post_url = post_entry['url']
                    if post_url in current_posts_by_url:
                        logging.warning(f"检测到重复 PDF 名称，后处理文件将覆盖先前记录: {post_url}")
                    current_posts_by_url[post_url] = post_entry
                except Exception as e:
                    had_errors = True
                    logging.error(f"处理 [{filename}] 失败: {e}")

    if had_errors:
        save_r2_manifest(r2_manifest)
        logging.error("存在 PDF 处理或上传失败，已跳过 posts.json 更新以保护现有索引")
        return False

    if not update_posts_json(current_posts_by_url, r2_config):
        save_r2_manifest(r2_manifest)
        return False

    prune_r2_manifest(r2_manifest, current_object_keys, r2_config, prefixes=['pdfs/'])
    save_r2_manifest(r2_manifest)
    cleanup_empty_directories(POSTS_BASE_DIR)
    return True
