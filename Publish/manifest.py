import json
import logging
import os

from .config import R2_MANIFEST_PATH, R2_MANIFEST_VERSION

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
