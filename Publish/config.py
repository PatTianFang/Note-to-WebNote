import os

WEBNOTE_ROOT = os.path.join('.', 'WebNote', 'PatTianFang.github.io')
ROOT_REPO = '.'
NOTE_ROOT = os.path.join('.', 'Note')
RECORDS_SOURCE_DIR = os.path.join(NOTE_ROOT, '记录')
IMAGES_DIR = os.path.join(WEBNOTE_ROOT, 'images')
RECORDS_JSON_PATH = os.path.join(WEBNOTE_ROOT, 'data', 'records.json')
RECORDS_DATA_JS_PATH = os.path.join(WEBNOTE_ROOT, 'js', 'records-data.js')
POSTS_BASE_DIR = os.path.join(WEBNOTE_ROOT, 'posts')
POSTS_JSON_PATH = os.path.join(WEBNOTE_ROOT, 'data', 'posts.json')
HTML_TEMPLATE_PATH = os.path.join(POSTS_BASE_DIR, 'demo', 'pdf-embed-demo.html')
STYLE_CSS_PATH = os.path.join(WEBNOTE_ROOT, 'css', 'style.css')
GENERATED_BY = 'Publish.py'
IMAGE_EXTENSIONS = {'.avif', '.gif', '.jpeg', '.jpg', '.png', '.svg', '.webp'}
RECORD_PLACE_COORDS = {
    '青岛': [36.0662, 120.3826],
    '厦门': [24.4798, 118.0894],
    '天津': [39.3434, 117.3616],
}
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
