#!/usr/bin/env python3
"""
检测 md 文档中未使用的图片并移动到 unused 文件夹
"""

import re
import os
import shutil
from pathlib import Path


def get_image_references(md_files):
    """从所有 md 文件中提取图片引用"""
    referenced_images = set()
    image_pattern = re.compile(r'!\[.*?\]\(([^)]+\.png)\)')

    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            matches = image_pattern.findall(content)
            for match in matches:
                referenced_images.add(os.path.basename(match))
    return referenced_images


def main():
    script_dir = Path(__file__).parent
    images_dir = script_dir / 'images'
    unused_dir = script_dir / 'unused'

    # 获取所有 md 文件
    md_files = list(script_dir.glob('*.md'))

    # 获取所有图片引用
    referenced = get_image_references(md_files)
    print(f"在 {len(md_files)} 个 md 文件中找到 {len(referenced)} 个图片引用")

    # 获取 images 目录下的所有 png 文件
    all_images = [f for f in images_dir.glob('*.png') if f.is_file()]
    print(f"images 目录共有 {len(all_images)} 个图片")

    # 找出未使用的图片
    unused_images = [img for img in all_images if img.name not in referenced]

    if not unused_images:
        print("没有未使用的图片")
        return

    print(f"发现 {len(unused_images)} 个未使用的图片:")
    for img in unused_images:
        print(f"  - {img.name}")

    # 创建未使用目录
    unused_dir.mkdir(exist_ok=True)

    # 移动未使用的图片
    for img in unused_images:
        dest = unused_dir / img.name
        # 防止文件名冲突
        if dest.exists():
            base, ext = Path(img.name).stem, Path(img.name).suffix
            counter = 1
            while dest.exists():
                dest = unused_dir / f"{base}_{counter}{ext}"
                counter += 1
        shutil.move(str(img), str(dest))
        print(f"已移动: {img.name} -> {dest.name}")

    print(f"\n完成! 已将 {len(unused_images)} 个未使用图片移动到 {unused_dir}/")


if __name__ == '__main__':
    main()