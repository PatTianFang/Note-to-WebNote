import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from urllib.parse import quote

WEBNOTE_ROOT = os.path.join('.', 'WebNote', 'PatTianFang.github.io')
POSTS_BASE_DIR = os.path.join(WEBNOTE_ROOT, 'posts')
POSTS_JSON_PATH = os.path.join(WEBNOTE_ROOT, 'data', 'posts.json')
HTML_TEMPLATE_PATH = os.path.join(POSTS_BASE_DIR, 'demo', 'pdf-embed-demo.html')
GENERATED_BY = 'Publish.py'
R2_BUCKET_ENV = 'WEBNOTE_R2_BUCKET'
R2_PUBLIC_BASE_URL_ENV = 'WEBNOTE_R2_PUBLIC_BASE_URL'
R2_CACHE_CONTROL_ENV = 'WEBNOTE_R2_CACHE_CONTROL'
DEFAULT_R2_CACHE_CONTROL = 'public, max-age=31536000'
LOCAL_ARTIFACT_PATHS = [
    os.path.join(WEBNOTE_ROOT, 'pdfs'),
    '.wrangler',
    '__pycache__',
    'build',
    'dist',
    'Publish.spec',
]


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


def is_inside_workspace(path):
    workspace_root = os.path.abspath('.')
    target_path = os.path.abspath(path)
    return os.path.commonpath([workspace_root, target_path]) == workspace_root


def remove_path_if_exists(path):
    if not os.path.exists(path):
        return True

    if not is_inside_workspace(path):
        logging.error(f"拒绝删除工作区外路径: {path}")
        return False

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        logging.info(f"清理生成产物: {path}")
        return True
    except Exception as e:
        logging.error(f"清理生成产物失败 [{path}]: {e}")
        return False


def cleanup_local_artifacts():
    ok = True
    for path in LOCAL_ARTIFACT_PATHS:
        ok = remove_path_if_exists(path) and ok
    return ok


def get_r2_config():
    bucket = os.environ.get(R2_BUCKET_ENV, '').strip()
    public_base_url = os.environ.get(R2_PUBLIC_BASE_URL_ENV, '').strip().rstrip('/')
    cache_control = os.environ.get(R2_CACHE_CONTROL_ENV, DEFAULT_R2_CACHE_CONTROL).strip()

    missing_envs = []
    if not bucket:
        missing_envs.append(R2_BUCKET_ENV)
    if not public_base_url:
        missing_envs.append(R2_PUBLIC_BASE_URL_ENV)

    if missing_envs:
        logging.error(
            "缺少 R2 配置环境变量: %s。示例: $env:%s='webnote-pdfs'; "
            "$env:%s='https://static.example.com'",
            ', '.join(missing_envs),
            R2_BUCKET_ENV,
            R2_PUBLIC_BASE_URL_ENV,
        )
        return None

    if not public_base_url.startswith(('http://', 'https://')):
        logging.error(f"{R2_PUBLIC_BASE_URL_ENV} 必须以 http:// 或 https:// 开头")
        return None

    wrangler_path = shutil.which('wrangler')
    if not wrangler_path:
        logging.error("未找到 wrangler。请先运行: npm install -g wrangler && wrangler login")
        return None

    return {
        'bucket': bucket,
        'public_base_url': public_base_url,
        'cache_control': cache_control,
        'wrangler_path': wrangler_path,
    }


def build_r2_object_key(category, filename):
    return f"pdfs/{category}/{filename}"


def build_public_pdf_url(public_base_url, object_key, version=None):
    encoded_key = quote(object_key.replace('\\', '/'), safe='/-._~')
    public_url = f"{public_base_url.rstrip('/')}/{encoded_key}"
    if version is not None:
        public_url = f"{public_url}?v={quote(str(version), safe='')}"
    return public_url


def run_wrangler(r2_config, args, action):
    command = [r2_config['wrangler_path'], *args]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        if result.stdout.strip():
            logging.debug(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ''
        stdout = e.stdout.strip() if e.stdout else ''
        logging.error(f"{action} 失败: {stderr or stdout or e}")
        return False


def upload_pdf_to_r2(r2_config, source_file, object_key):
    args = [
        'r2',
        'object',
        'put',
        f"{r2_config['bucket']}/{object_key}",
        '--file',
        source_file,
        '--content-type',
        'application/pdf',
        '--cache-control',
        r2_config['cache_control'],
        '--remote',
    ]
    return run_wrangler(r2_config, args, f"上传 R2 对象 {object_key}")


def delete_r2_object(r2_config, object_key):
    args = ['r2', 'object', 'delete', f"{r2_config['bucket']}/{object_key}", '--remote']
    return run_wrangler(r2_config, args, f"删除 R2 对象 {object_key}")


def run_git(args, action):
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=WEBNOTE_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        if result.stdout.strip():
            logging.info(result.stdout.strip())
        return result
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ''
        stdout = e.stdout.strip() if e.stdout else ''
        logging.error(f"{action} 失败: {stderr or stdout or e}")
        return None


def deploy_webnote_repo():
    if not os.path.isdir(os.path.join(WEBNOTE_ROOT, '.git')):
        logging.error(f"WebNote Git 仓库不存在: {WEBNOTE_ROOT}")
        return False

    status_before = run_git(['status', '--porcelain'], '检查 Git 状态')
    if status_before is None:
        return False

    if not status_before.stdout.strip():
        logging.info('WebNote 没有需要提交的变更')
        return True

    if run_git(['add', '.'], '暂存 WebNote 变更') is None:
        return False

    status_after_add = run_git(['status', '--porcelain'], '检查暂存后的 Git 状态')
    if status_after_add is None:
        return False

    if not status_after_add.stdout.strip():
        logging.info('WebNote 没有需要提交的变更')
        return True

    commit_message = f"Publish notes {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if run_git(['commit', '-m', commit_message], '提交 WebNote 变更') is None:
        return False

    if run_git(['push'], '推送 WebNote 变更') is None:
        return False

    logging.info('WebNote 已提交并推送，Cloudflare Pages 将自动部署')
    return True


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


def delete_generated_assets(post, r2_config):
    url = post.get('url', '')
    category = post.get('category', '')
    html_name = url.rsplit('/', 1)[-1]
    pdf_name = f"{os.path.splitext(html_name)[0]}.pdf"

    html_path = os.path.join(WEBNOTE_ROOT, *url.split('/'))
    object_key = build_r2_object_key(category, pdf_name)

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
    except Exception as e:
        logging.error(f"更新 posts.json 失败: {e}")


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

    current_posts_by_url = {}
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
                target_html_file = os.path.join(target_posts_dir, f'{pdf_name_no_ext}.html')

                try:
                    st = os.stat(source_file)
                    create_time_str = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d')
                    object_key = build_r2_object_key(item, filename)
                    pdf_version = int(st.st_mtime)
                    pdf_url = build_public_pdf_url(r2_config['public_base_url'], object_key, pdf_version)

                    if not upload_pdf_to_r2(r2_config, source_file, object_key):
                        had_errors = True
                        continue
                    logging.info(f"PDF 上传 R2 成功: {object_key}")

                    embed_tag = (
                        f'<embed src="{pdf_url}" '
                        f'type="application/pdf" width="100%" height="800px">'
                    )

                    content = html_template
                    content = content.replace('模板修改1', pdf_name_no_ext)
                    content = content.replace('模板修改2', create_time_str)
                    content = content.replace('模板修改3', item)
                    content = content.replace('模板修改4', f'关于 {pdf_name_no_ext} 的详细内容。')
                    content = content.replace('模板修改5', embed_tag)
                    content = content.replace('模板修改6', pdf_url)

                    with open(target_html_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logging.info(f"HTML 创建成功: {pdf_name_no_ext}.html")

                    post_entry = build_post_entry(pdf_name_no_ext, item, create_time_str)
                    post_url = post_entry['url']
                    if post_url in current_posts_by_url:
                        logging.warning(f"检测到重复 PDF 名称，后处理文件将覆盖先前记录: {post_url}")
                    current_posts_by_url[post_url] = post_entry
                except Exception as e:
                    had_errors = True
                    logging.error(f"处理 [{filename}] 失败: {e}")

    if had_errors:
        logging.error("存在 PDF 处理或上传失败，已跳过 posts.json 更新以保护现有索引")
        return False

    update_posts_json(current_posts_by_url, r2_config)
    return True


if __name__ == '__main__':
    setup_logging()
    logging.info('开始同步 PDF 文件...')
    cleanup_local_artifacts()
    if sync_pdf_files() and cleanup_local_artifacts() and deploy_webnote_repo():
        logging.info('同步完成。')
    else:
        logging.error('同步未完成。')
