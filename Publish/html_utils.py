import html
import re

from .paths import build_css_href_for_url, build_recall_href_for_url

def html_escape(value):
    return html.escape(str(value), quote=True)

def build_footer_html(page_url):
    recall_href = html_escape(build_recall_href_for_url(page_url))
    return f'''<footer>
        <div class="container">
            <p>&copy; 2026 FangTian's Note | 基于纯 HTML/CSS/JS 构建 | <a href="{recall_href}">回忆</a></p>
        </div>
    </footer>'''

def refresh_css_href(content, page_url):
    css_href = html_escape(build_css_href_for_url(page_url))
    return re.sub(
        r'<link\s+rel="stylesheet"\s+href="[^"]*css/style\.css(?:\?v=[^"]*)?">',
        f'<link rel="stylesheet" href="{css_href}">',
        content,
        count=1,
        flags=re.IGNORECASE,
    )

def refresh_footer(content, page_url):
    footer_html = build_footer_html(page_url)
    updated, count = re.subn(
        r'<footer>[\s\S]*?</footer>',
        footer_html,
        content,
        count=1,
        flags=re.IGNORECASE,
    )
    return updated if count else content

def refresh_common_page_chrome(content, page_url):
    content = refresh_css_href(content, page_url)
    return refresh_footer(content, page_url)

def strip_html_tags(value):
    return re.sub(r'<[^>]+>', '', str(value))

def clean_html_text(value):
    return html.unescape(strip_html_tags(value)).replace('\xa0', ' ').strip()
