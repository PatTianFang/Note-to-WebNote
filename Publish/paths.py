import os
import posixpath
from urllib.parse import quote

from .config import STYLE_CSS_PATH
from datetime import datetime

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

def build_recall_href_for_url(page_url):
    return build_relative_url(page_url, 'recall/university/')
