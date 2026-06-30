import logging
import os
import shutil

from .config import LOCAL_ARTIFACT_PATHS

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
