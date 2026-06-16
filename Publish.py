import hashlib
import html
import json
import logging
import os
import posixpath
import re
import shutil
import subprocess
from datetime import datetime
from urllib import error, request
from urllib.parse import quote, unquote

WEBNOTE_ROOT = os.path.join('.', 'WebNote', 'PatTianFang.github.io')
ROOT_REPO = '.'
NOTE_ROOT = os.path.join('.', 'Note')
RECORDS_SOURCE_DIR = os.path.join(NOTE_ROOT, '记录')
IMAGES_DIR = os.path.join(WEBNOTE_ROOT, 'images')
RECORDS_JSON_PATH = os.path.join(WEBNOTE_ROOT, 'data', 'records.json')
POSTS_BASE_DIR = os.path.join(WEBNOTE_ROOT, 'posts')
POSTS_JSON_PATH = os.path.join(WEBNOTE_ROOT, 'data', 'posts.json')
HTML_TEMPLATE_PATH = os.path.join(POSTS_BASE_DIR, 'demo', 'pdf-embed-demo.html')
STYLE_CSS_PATH = os.path.join(WEBNOTE_ROOT, 'css', 'style.css')
GENERATED_BY = 'Publish.py'
IMAGE_EXTENSIONS = {'.avif', '.gif', '.jpeg', '.jpg', '.png', '.svg', '.webp'}
NOTE_REMOTE_URL = 'https://github.com/PatTianFang/Note.git'
ROOT_REMOTE_URL = 'https://github.com/PatTianFang/Note-to-WebNote.git'
NOTE_BRANCH = 'main'
R2_BUCKET_ENV = 'WEBNOTE_R2_BUCKET'
R2_PUBLIC_BASE_URL_ENV = 'WEBNOTE_R2_PUBLIC_BASE_URL'
R2_CACHE_CONTROL_ENV = 'WEBNOTE_R2_CACHE_CONTROL'
WRANGLER_TIMEOUT_ENV = 'WEBNOTE_WRANGLER_TIMEOUT_SECONDS'
DEFAULT_R2_CACHE_CONTROL = 'public, max-age=31536000'
DEFAULT_WRANGLER_TIMEOUT_SECONDS = 600
R2_MANIFEST_PATH = '.webnote-r2-manifest.json'
R2_MANIFEST_VERSION = 1
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


def cleanup_empty_directories(base_dir):
    if not os.path.isdir(base_dir):
        return True

    ok = True
    for root, _dirs, _files in os.walk(base_dir, topdown=False):
        if os.path.abspath(root) == os.path.abspath(base_dir):
            continue
        if not is_inside_workspace(root):
            logging.error(f"Refuse to remove empty directory outside workspace: {root}")
            ok = False
            continue
        try:
            if os.listdir(root):
                continue
        except OSError as e:
            logging.warning(f"Failed to inspect directory [{root}]: {e}")
            ok = False
            continue
        try:
            os.rmdir(root)
            logging.info(f"Removed empty directory: {root}")
        except OSError as e:
            logging.warning(f"Failed to remove empty directory [{root}]: {e}")
            ok = False
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


def build_r2_object_key_from_source(source_file, source_base_dir):
    rel_path = os.path.relpath(source_file, source_base_dir).replace(os.sep, '/')
    return f"pdfs/{rel_path}"


def build_post_url_from_source(source_file, source_base_dir):
    rel_path = os.path.relpath(source_file, source_base_dir)
    rel_html_path = f"{os.path.splitext(rel_path)[0]}.html"
    return f"posts/{rel_html_path.replace(os.sep, '/')}"


def build_site_root_prefix(post_url):
    directory = os.path.dirname(post_url.replace('/', os.sep))
    depth = len([part for part in directory.split(os.sep) if part])
    return '../' * depth


def build_public_pdf_url(public_base_url, object_key, version=None):
    encoded_key = quote(object_key.replace('\\', '/'), safe='/-._~')
    public_url = f"{public_base_url.rstrip('/')}/{encoded_key}"
    if version is not None:
        public_url = f"{public_url}?v={quote(str(version), safe='')}"
    return public_url


def load_r2_manifest():
    if not os.path.exists(R2_MANIFEST_PATH):
        return {}
    try:
        with open(R2_MANIFEST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Failed to read R2 manifest, rebuilding it: {e}")
        return {}


def save_r2_manifest(manifest):
    try:
        with open(R2_MANIFEST_PATH, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception as e:
        logging.warning(f"Failed to write R2 manifest: {e}")


def build_source_signature(source_file):
    st = os.stat(source_file)
    return {
        'version': R2_MANIFEST_VERSION,
        'size': st.st_size,
        'mtime_ns': st.st_mtime_ns,
    }


def manifest_entry_matches_source(manifest, object_key, source_file):
    entry = manifest.get(object_key)
    if not entry:
        return False
    return entry == build_source_signature(source_file)


def update_manifest_entry(manifest, object_key, source_file):
    manifest[object_key] = build_source_signature(source_file)


def prune_r2_manifest(manifest, current_object_keys, r2_config):
    stale_object_keys = sorted(set(manifest) - current_object_keys)
    for object_key in stale_object_keys:
        if delete_r2_object(r2_config, object_key):
            manifest.pop(object_key, None)
            logging.info(f"Removed stale R2 manifest entry: {object_key}")


def get_file_md5(file_path):
    digest = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def get_remote_headers(url):
    try:
        req = request.Request(
            url,
            method='HEAD',
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        with request.urlopen(req, timeout=20) as response:
            return response.headers
    except error.HTTPError as e:
        if e.code == 404:
            return None
        logging.warning(f"R2 object HEAD returned HTTP {e.code}: {url}")
        return None
    except Exception as e:
        logging.warning(f"R2 object HEAD failed [{url}]: {e}")
        return None


def r2_object_matches_source(source_file, public_url):
    headers = get_remote_headers(public_url)
    if not headers:
        return False

    remote_length = headers.get('Content-Length')
    if remote_length:
        try:
            if int(remote_length) != os.path.getsize(source_file):
                return False
        except ValueError:
            return False

    remote_etag = headers.get('ETag', '').strip('"').lower()
    if len(remote_etag) != 32:
        return False

    return remote_etag == get_file_md5(source_file)


def run_wrangler(r2_config, args, action):
    command = [r2_config['wrangler_path'], *args]
    try:
        timeout_seconds = int(os.environ.get(WRANGLER_TIMEOUT_ENV, DEFAULT_WRANGLER_TIMEOUT_SECONDS))
    except ValueError:
        timeout_seconds = DEFAULT_WRANGLER_TIMEOUT_SECONDS

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=timeout_seconds,
        )
        if result.stdout.strip():
            logging.debug(result.stdout.strip())
        return True
    except subprocess.TimeoutExpired:
        logging.error(f"{action} timed out after {timeout_seconds} seconds")
        return False
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ''
        stdout = e.stdout.strip() if e.stdout else ''
        logging.error(f"{action} 失败: {stderr or stdout or e}")
        return False


def upload_pdf_to_r2(r2_config, source_file, object_key, manifest):
    if manifest_entry_matches_source(manifest, object_key, source_file):
        logging.info(f"PDF unchanged locally, skipped R2 check: {object_key}")
        return True

    public_url = build_public_pdf_url(r2_config['public_base_url'], object_key)
    if r2_object_matches_source(source_file, public_url):
        update_manifest_entry(manifest, object_key, source_file)
        logging.info(f"PDF unchanged in R2, skipped upload: {object_key}")
        return True

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
    upload_ok = run_wrangler(r2_config, args, f"Upload R2 object {object_key}")
    if upload_ok:
        update_manifest_entry(manifest, object_key, source_file)
        return True

    if r2_object_matches_source(source_file, public_url):
        update_manifest_entry(manifest, object_key, source_file)
        logging.warning(f"Wrangler returned failure, but R2 object is current: {object_key}")
        return True

    return False


def delete_r2_object(r2_config, object_key):
    args = ['r2', 'object', 'delete', f"{r2_config['bucket']}/{object_key}", '--remote']
    return run_wrangler(r2_config, args, f"删除 R2 对象 {object_key}")


def run_git(args, action, repo_path=WEBNOTE_ROOT, check=True):
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=repo_path,
            check=check,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        stdout = result.stdout.strip()
        if stdout:
            line_count = stdout.count('\n') + 1
            if len(stdout) > 2000 or line_count > 40:
                logging.info(f"{action} output omitted ({line_count} lines, {len(stdout)} chars)")
            else:
                logging.info(stdout)
        return result
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ''
        stdout = e.stdout.strip() if e.stdout else ''
        logging.error(f"{action} 失败: {stderr or stdout or e}")
        return None


def ensure_git_repo(repo_path, repo_label, init_if_missing=False, branch=None):
    if not os.path.isdir(repo_path):
        logging.error(f"{repo_label} path does not exist: {repo_path}")
        return False

    git_dir = os.path.join(repo_path, '.git')
    if os.path.isdir(git_dir):
        return True

    if not init_if_missing:
        logging.error(f"{repo_label} Git repository does not exist: {repo_path}")
        return False

    if run_git(['init'], f'init {repo_label} repo', repo_path=repo_path) is None:
        return False

    if branch and run_git(['branch', '-M', branch], f'set {repo_label} branch', repo_path=repo_path) is None:
        return False

    return True


def get_origin_url(repo_path):
    result = subprocess.run(
        ['git', 'remote', 'get-url', 'origin'],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def ensure_origin_remote(repo_path, repo_label, remote_url):
    current_remote = get_origin_url(repo_path)
    if not current_remote:
        return run_git(
            ['remote', 'add', 'origin', remote_url],
            f'add {repo_label} origin',
            repo_path=repo_path,
        ) is not None

    if current_remote != remote_url:
        return run_git(
            ['remote', 'set-url', 'origin', remote_url],
            f'update {repo_label} origin',
            repo_path=repo_path,
        ) is not None

    return True


def copy_git_identity(source_repo_path, target_repo_path):
    for key in ('user.name', 'user.email'):
        source_value = subprocess.run(
            ['git', 'config', key],
            cwd=source_repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        if source_value.returncode != 0 or not source_value.stdout.strip():
            continue

        if run_git(
            ['config', key, source_value.stdout.strip()],
            f'set Git {key}',
            repo_path=target_repo_path,
        ) is None:
            return False

    return True


def get_current_branch(repo_path, fallback_branch=None):
    result = run_git(['branch', '--show-current'], 'get current Git branch', repo_path=repo_path)
    if result is None:
        return fallback_branch

    branch = result.stdout.strip()
    return branch or fallback_branch


def commit_and_push_repo(repo_path, repo_label, remote_url=None, branch=None, init_if_missing=False):
    if not ensure_git_repo(repo_path, repo_label, init_if_missing=init_if_missing, branch=branch):
        return False

    if not copy_git_identity(ROOT_REPO, repo_path):
        return False

    if branch and run_git(['branch', '-M', branch], f'set {repo_label} branch', repo_path=repo_path) is None:
        return False

    if remote_url and not ensure_origin_remote(repo_path, repo_label, remote_url):
        return False

    status_before = run_git(['status', '--porcelain'], f'check {repo_label} status', repo_path=repo_path)
    if status_before is None:
        return False

    if not status_before.stdout.strip():
        logging.info(f'{repo_label} has no changes to commit')
        return True

    if run_git(['add', '.'], f'stage {repo_label} changes', repo_path=repo_path) is None:
        return False

    status_after_add = run_git(['status', '--porcelain'], f'check staged {repo_label} status', repo_path=repo_path)
    if status_after_add is None:
        return False

    if not status_after_add.stdout.strip():
        logging.info(f'{repo_label} has no changes to commit')
        return True

    commit_message = f"Publish {repo_label} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if run_git(['commit', '-m', commit_message], f'commit {repo_label} changes', repo_path=repo_path) is None:
        return False

    push_branch = branch or get_current_branch(repo_path)
    push_args = ['push']
    if push_branch:
        push_args = ['push', '-u', 'origin', push_branch]

    if run_git(push_args, f'push {repo_label} changes', repo_path=repo_path) is None:
        return False

    logging.info(f'{repo_label} committed and pushed')
    return True


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


def deploy_note_repo():
    return commit_and_push_repo(
        NOTE_ROOT,
        'Note',
        remote_url=NOTE_REMOTE_URL,
        branch=NOTE_BRANCH,
        init_if_missing=True,
    )


def deploy_root_repo():
    return commit_and_push_repo(
        ROOT_REPO,
        'Note-to-WebNote',
        remote_url=ROOT_REMOTE_URL,
    )


def deploy_git_repositories():
    return deploy_webnote_repo() and deploy_note_repo() and deploy_root_repo()


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


def html_escape(value):
    return html.escape(str(value), quote=True)


def url_path_join(*parts):
    return '/'.join(quote(str(part).replace('\\', '/'), safe='/-._~') for part in parts)


def quote_url_path(path):
    return quote(str(path).replace('\\', '/'), safe='/-._~')


def build_relative_url(source_url, target_url):
    source_dir = posixpath.dirname(source_url.replace('\\', '/')) or '.'
    rel_url = posixpath.relpath(target_url.replace('\\', '/'), source_dir)
    return quote_url_path(rel_url)


def get_style_version():
    try:
        return str(int(os.path.getmtime(STYLE_CSS_PATH)))
    except OSError:
        return datetime.now().strftime('%Y%m%d%H%M%S')


def build_css_href_for_url(page_url):
    return f"{build_relative_url(page_url, 'css/style.css')}?v={get_style_version()}"


def refresh_css_href(content, page_url):
    css_href = html_escape(build_css_href_for_url(page_url))
    return re.sub(
        r'<link\s+rel="stylesheet"\s+href="[^"]*css/style\.css(?:\?v=[^"]*)?">',
        f'<link rel="stylesheet" href="{css_href}">',
        content,
        count=1,
        flags=re.IGNORECASE,
    )


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


def convert_record_markdown_to_html(markdown_text, record_name, image_filenames):
    image_names = set(image_filenames)
    referenced_images = []

    def replace_image(match):
        image_name = match.group(1).strip()
        if image_name in image_names:
            referenced_images.append(image_name)
            src = url_path_join(record_name, image_name)
            alt = os.path.splitext(image_name)[0]
            return f'\n<figure class="record-auto-photo"><img src="{src}" alt="{html_escape(alt)}"></figure>\n'
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
        src = url_path_join(record_name, image_name)
        alt = os.path.splitext(image_name)[0]
        blocks.append(f'<figure class="record-auto-photo"><img src="{src}" alt="{html_escape(alt)}"></figure>')

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

    <footer>
        <div class="container">
            <p>&copy; 2026 FangTian's Note | 基于纯 HTML/CSS/JS 构建</p>
        </div>
    </footer>
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

    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(RECORDS_JSON_PATH), exist_ok=True)
    records = []
    current_urls = set()

    for record_name in sorted(os.listdir(RECORDS_SOURCE_DIR)):
        record_dir = os.path.join(RECORDS_SOURCE_DIR, record_name)
        if not os.path.isdir(record_dir):
            continue

        try:
            target_asset_dir = os.path.join(IMAGES_DIR, record_name)
            image_filenames = copy_record_assets(record_dir, target_asset_dir)
            markdown_path = get_record_markdown(record_dir, record_name)
            markdown_text = ''
            if markdown_path:
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()

            body_html, _referenced_images = convert_record_markdown_to_html(
                markdown_text,
                record_name,
                image_filenames,
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
            records.append({
                'id': record_name,
                'title': record_name,
                'date': create_time_str,
                'display_date': display_date,
                'place': record_info.get('place') or record_name,
                'url': url_path_join('images', f'{record_name}.html'),
                'excerpt': f'{display_date}，拍摄地点：{record_info.get("place") or record_name}，共 {len(image_filenames)} 张图片。',
                'cover': url_path_join('images', record_name, first_image) if first_image else '',
                'generated_by': GENERATED_BY,
            })
            current_urls.add(records[-1]['url'])
            logging.info(f"记录页生成成功: {target_html_file}")
        except Exception as e:
            logging.error(f"处理记录文件夹失败 [{record_name}]: {e}")
            return False

    if not cleanup_stale_record_pages(current_urls):
        return False

    records.sort(key=lambda item: item.get('date', ''), reverse=True)
    with open(RECORDS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=4)
    logging.info(f"更新 records.json 成功，共 {len(records)} 条记录")
    return True


PAGE_NAV_PATTERN = re.compile(
    r'\s*<!-- BEGIN PUBLISH PAGE NAV -->[\s\S]*?<!-- END PUBLISH PAGE NAV -->\s*',
    re.IGNORECASE,
)


def strip_html_tags(value):
    return re.sub(r'<[^>]+>', '', str(value))


def clean_html_text(value):
    return html.unescape(strip_html_tags(value)).replace('\xa0', ' ').strip()


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

                    site_root_prefix = build_site_root_prefix(post_url)
                    content = content.replace('../../css/style.css', build_css_href_for_url(post_url))
                    content = content.replace('../../js/theme.js', f'{site_root_prefix}js/theme.js')
                    content = content.replace('../../index.html', f'{site_root_prefix}index.html')
                    content = content.replace('../../records.html', f'{site_root_prefix}records.html')
                    content = content.replace('../../about.html', f'{site_root_prefix}about.html')

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

    prune_r2_manifest(r2_manifest, current_object_keys, r2_config)
    save_r2_manifest(r2_manifest)
    cleanup_empty_directories(POSTS_BASE_DIR)
    return True


if __name__ == '__main__':
    setup_logging()
    logging.info('开始同步 PDF 文件...')
    cleanup_local_artifacts()
    if sync_record_pages() and sync_pdf_files() and sync_page_navigation() and cleanup_local_artifacts() and deploy_git_repositories():
        logging.info('同步完成。')
    else:
        logging.error('同步未完成。')
