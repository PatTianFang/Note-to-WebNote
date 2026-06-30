import logging

from .cleanup import cleanup_local_artifacts
from .footers import sync_site_footers
from .git_ops import deploy_git_repositories
from .logging_utils import setup_logging
from .page_nav import sync_page_navigation
from .pdf_posts import sync_pdf_files
from .records import sync_record_pages

def main():
    setup_logging()
    logging.info('开始同步 PDF 文件...')
    cleanup_local_artifacts()
    if sync_record_pages() and sync_pdf_files() and sync_page_navigation() and sync_site_footers() and cleanup_local_artifacts() and deploy_git_repositories():
        logging.info('同步完成。')
        return 0
    logging.error('同步未完成。')
    return 1


