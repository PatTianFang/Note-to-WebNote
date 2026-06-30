import json
import logging
import os

from .config import GENERATED_BY, POSTS_JSON_PATH, WEBNOTE_ROOT
from .r2 import build_r2_object_key, delete_r2_object

def build_post_entry(pdf_name_no_ext, category, create_time_str, post_url, object_key):
    return {
        'id': pdf_name_no_ext,
        'title': pdf_name_no_ext,
        'date': create_time_str,
        'category': category,
        'url': post_url,
        'excerpt': f'这是关于 {pdf_name_no_ext} 的 PDF 文档预览。',
        'r2_object_key': object_key,
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

def delete_generated_assets(post, r2_config):
    url = post.get('url', '')
    category = post.get('category', '')
    html_name = url.rsplit('/', 1)[-1]
    pdf_name = f"{os.path.splitext(html_name)[0]}.pdf"

    html_path = os.path.join(WEBNOTE_ROOT, *url.split('/'))
    object_key = post.get('r2_object_key') or build_r2_object_key(category, pdf_name)

    delete_file_if_exists(html_path)
    delete_r2_object(r2_config, object_key)

def update_posts_json(current_posts_by_url, r2_config):
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
                    delete_generated_assets(post, r2_config)
                    logging.info(f"删除 posts.json 中已失效的记录: {post_url}")
            else:
                merged_data.append(post)

        for post_url, post in current_posts_by_url.items():
            if post_url not in handled_urls:
                merged_data.append(post)

        with open(POSTS_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=4)

        logging.info('更新 posts.json 成功')
        return True
    except Exception as e:
        logging.error(f"更新 posts.json 失败: {e}")
        return False
