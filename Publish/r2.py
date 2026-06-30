import hashlib
import logging
import mimetypes
import os
import shutil
import subprocess
from urllib import error, request
from urllib.parse import quote

from .config import (
    DEFAULT_R2_CACHE_CONTROL,
    DEFAULT_WRANGLER_TIMEOUT_SECONDS,
    R2_BUCKET_ENV,
    R2_CACHE_CONTROL_ENV,
    R2_PUBLIC_BASE_URL_ENV,
    WRANGLER_TIMEOUT_ENV,
)
from .manifest import manifest_entry_matches_source, update_manifest_entry

def build_r2_object_key(category, filename):
    return f"pdfs/{category}/{filename}"

def build_r2_object_key_from_source(source_file, source_base_dir):
    rel_path = os.path.relpath(source_file, source_base_dir).replace(os.sep, '/')
    return f"pdfs/{rel_path}"

def build_record_image_object_key(record_name, image_name):
    return f"images/{record_name}/{image_name}"

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

def build_public_r2_url(public_base_url, object_key, version=None):
    encoded_key = quote(object_key.replace('\\', '/'), safe='/-._~')
    public_url = f"{public_base_url.rstrip('/')}/{encoded_key}"
    if version is not None:
        public_url = f"{public_url}?v={quote(str(version), safe='')}"
    return public_url

def build_public_pdf_url(public_base_url, object_key, version=None):
    return build_public_r2_url(public_base_url, object_key, version)

def prune_r2_manifest(manifest, current_object_keys, r2_config, prefixes=None):
    manifest_keys = set(manifest)
    if prefixes:
        manifest_keys = {
            object_key
            for object_key in manifest_keys
            if any(object_key.startswith(prefix) for prefix in prefixes)
        }
    stale_object_keys = sorted(manifest_keys - current_object_keys)
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

def guess_content_type(source_file):
    content_type, _encoding = mimetypes.guess_type(source_file)
    return content_type or 'application/octet-stream'

def upload_file_to_r2(r2_config, source_file, object_key, manifest, content_type, label):
    if manifest_entry_matches_source(manifest, object_key, source_file):
        logging.info(f"{label} unchanged locally, skipped R2 check: {object_key}")
        return True

    public_url = build_public_r2_url(r2_config['public_base_url'], object_key)
    if r2_object_matches_source(source_file, public_url):
        update_manifest_entry(manifest, object_key, source_file)
        logging.info(f"{label} unchanged in R2, skipped upload: {object_key}")
        return True

    args = [
        'r2',
        'object',
        'put',
        f"{r2_config['bucket']}/{object_key}",
        '--file',
        source_file,
        '--content-type',
        content_type,
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

def upload_pdf_to_r2(r2_config, source_file, object_key, manifest):
    return upload_file_to_r2(
        r2_config,
        source_file,
        object_key,
        manifest,
        'application/pdf',
        'PDF',
    )

def upload_image_to_r2(r2_config, source_file, object_key, manifest):
    return upload_file_to_r2(
        r2_config,
        source_file,
        object_key,
        manifest,
        guess_content_type(source_file),
        'Image',
    )

def delete_r2_object(r2_config, object_key):
    args = ['r2', 'object', 'delete', f"{r2_config['bucket']}/{object_key}", '--remote']
    return run_wrangler(r2_config, args, f"删除 R2 对象 {object_key}")
