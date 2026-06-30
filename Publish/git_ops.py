import logging
import os
import subprocess
from datetime import datetime

from .config import NOTE_BRANCH, NOTE_REMOTE_URL, NOTE_ROOT, ROOT_REMOTE_URL, ROOT_REPO, WEBNOTE_ROOT

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
