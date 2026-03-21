import json
import logging
import os
import shutil
from datetime import datetime

WEBNOTE_ROOT = os.path.join('.', 'WebNote', 'PatTianFang.github.io')
POSTS_BASE_DIR = os.path.join(WEBNOTE_ROOT, 'posts')
PDFS_BASE_DIR = os.path.join(WEBNOTE_ROOT, 'pdfs')
POSTS_JSON_PATH = os.path.join(WEBNOTE_ROOT, 'data', 'posts.json')
HTML_TEMPLATE_PATH = os.path.join(POSTS_BASE_DIR, 'demo', 'pdf-embed-demo.html')
GENERATED_BY = 'Publish.py'


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def get_html_template():
    try:
        with open(HTML_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"读取 HTML 模板失败: {e}")
        return ""


def build_post_entry(pdf_name_no_ext, category, create_time_str):
    return {
        'id': pdf_name_no_ext,
        'title': pdf_name_no_ext,
        'date': create_time_str,
        'category': category,
        'url': f'posts/{category}/{pdf_name_no_ext}.html',
        'excerpt': f'这是关于 {pdf_name_no_ext} 的 PDF 文档预览。',
        'generated_by': GENERATED_BY,
    }


def is_generated_post(post):
    post_id = post.get('id', '')
    category = post.get('category', '')
    url = post.get('url', '')
    excerpt = post.get('excerpt', '')

    expected_url = f'posts/{category}/{post_id}.html'
    expected_excerpt = f'这是关于 {post_id} 的 PDF 文档预览。'

    return post.get('generated_by') == GENERATED_BY or (
        url == expected_url and excerpt == expected_excerpt
    )


def delete_file_if_exists(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"删除文件: {file_path}")
    except Exception as e:
        logging.error(f"删除文件失败 [{file_path}]: {e}")


def delete_generated_assets(post):
    url = post.get('url', '')
    category = post.get('category', '')
    html_name = os.path.basename(url)
    pdf_name = f"{os.path.splitext(html_name)[0]}.pdf"

    html_path = os.path.join(WEBNOTE_ROOT, *url.split('/'))
    pdf_path = os.path.join(PDFS_BASE_DIR, category, pdf_name)

    delete_file_if_exists(html_path)
    delete_file_if_exists(pdf_path)


def update_posts_json(current_posts_by_url):
    try:
        existing_data = []
        if os.path.exists(POSTS_JSON_PATH):
            with open(POSTS_JSON_PATH, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

        merged_data = []
        handled_urls = set()

        for post in existing_data:
            post_url = post.get('url', '')
            if is_generated_post(post):
                if post_url in current_posts_by_url:
                    merged_data.append(current_posts_by_url[post_url])
                    handled_urls.add(post_url)
                else:
                    delete_generated_assets(post)
                    logging.info(f"删除 posts.json 中已失效的记录: {post_url}")
            else:
                merged_data.append(post)

        for post_url, post in current_posts_by_url.items():
            if post_url not in handled_urls:
                merged_data.append(post)

        with open(POSTS_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=4)

        logging.info('更新 posts.json 成功')
    except Exception as e:
        logging.error(f"更新 posts.json 失败: {e}")


def sync_pdf_files():
    source_base_dir = os.path.join('.', 'Note')

    if not os.path.exists(source_base_dir):
        logging.error(f"源目录不存在: {source_base_dir}")
        return

    html_template = get_html_template()
    if not html_template:
        return

    current_posts_by_url = {}

    try:
        items = os.listdir(source_base_dir)
    except Exception as e:
        logging.error(f"无法读取源目录: {e}")
        return

    for item in items:
        source_category_dir = os.path.join(source_base_dir, item)
        if not os.path.isdir(source_category_dir):
            continue

        target_posts_dir = os.path.join(POSTS_BASE_DIR, item)
        target_pdfs_dir = os.path.join(PDFS_BASE_DIR, item)

        for target_dir in [target_posts_dir, target_pdfs_dir]:
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                logging.error(f"创建目标文件夹失败 [{target_dir}]: {e}")
                continue

        for root, dirs, files in os.walk(source_category_dir):
            for filename in files:
                if not filename.lower().endswith('.pdf'):
                    continue

                source_file = os.path.join(root, filename)
                pdf_name_no_ext = os.path.splitext(filename)[0]
                target_pdf_file = os.path.join(target_pdfs_dir, filename)
                target_html_file = os.path.join(target_posts_dir, f'{pdf_name_no_ext}.html')

                try:
                    st = os.stat(source_file)
                    create_time_str = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d')

                    if (
                        not os.path.exists(target_pdf_file)
                        or os.path.getmtime(source_file) > os.path.getmtime(target_pdf_file) + 1
                    ):
                        shutil.copy(source_file, target_pdf_file)
                        os.utime(target_pdf_file, (st.st_atime, st.st_mtime))
                        logging.info(f"PDF 复制成功: {filename}")
                    else:
                        logging.info(f"跳过 PDF 复制: {filename}")

                    embed_tag = (
                        f'<embed src="../../pdfs/{item}/{filename}" '
                        f'type="application/pdf" width="100%" height="800px">'
                    )

                    content = html_template
                    content = content.replace('模板修改1', pdf_name_no_ext)
                    content = content.replace('模板修改2', create_time_str)
                    content = content.replace('模板修改3', item)
                    content = content.replace('模板修改4', f'关于 {pdf_name_no_ext} 的详细内容。')
                    content = content.replace('模板修改5', embed_tag)

                    with open(target_html_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logging.info(f"HTML 创建成功: {pdf_name_no_ext}.html")

                    post_entry = build_post_entry(pdf_name_no_ext, item, create_time_str)
                    post_url = post_entry['url']
                    if post_url in current_posts_by_url:
                        logging.warning(f"检测到重复 PDF 名称，后处理文件将覆盖先前记录: {post_url}")
                    current_posts_by_url[post_url] = post_entry
                except Exception as e:
                    logging.error(f"处理 [{filename}] 失败: {e}")

    update_posts_json(current_posts_by_url)


if __name__ == '__main__':
    setup_logging()
    logging.info('开始同步 PDF 文件...')
    sync_pdf_files()
    logging.info('同步完成。')
