#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
使用 OpenCV 实时显示摄像头画面。

运行方式：
    python3 camera_preview.py

退出方式：
    在图像窗口中按 q 或 Esc。
"""

import sys

import cv2


def main():
    # 摄像头编号。
    # 0 表示默认摄像头，一般对应 /dev/video0。
    # 如果系统只有一个 USB 摄像头，通常使用 0 就可以打开。
    camera_index = 0

    # 创建窗口标题。
    # 这个名字会显示在 OpenCV 弹出的摄像头画面窗口上。
    window_name = "OpenCV Camera Preview"

    # 使用 VideoCapture 打开摄像头。
    # CAP_V4L2 是 Linux 下常用的视频采集后端，适合 /dev/video* 设备。
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)

    # 如果指定 V4L2 后端打开失败，就再用 OpenCV 默认方式尝试一次。
    # 这样可以提高在不同摄像头/驱动上的兼容性。
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(camera_index)

    # 如果两次都打不开，说明摄像头设备不可用、被占用，或者权限不足。
    if not cap.isOpened():
        print("错误：无法打开摄像头。", file=sys.stderr)
        print("请检查摄像头是否连接，或 /dev/video0 是否存在。", file=sys.stderr)
        return 1

    # 设置期望的画面分辨率。
    # 摄像头不一定支持所有分辨率，如果设置失败，OpenCV 会继续使用默认分辨率。
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 创建一个可调整大小的窗口。
    # WINDOW_NORMAL 表示窗口大小可以被鼠标拖动改变。
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    print("摄像头窗口已打开。")
    print("在窗口中按 q 或 Esc 退出。")

    try:
        # 不断读取摄像头画面，形成实时视频预览。
        while True:
            # cap.read() 会返回两个值：
            # ret: 是否成功读取到一帧画面
            # frame: 读取到的图像数据
            ret, frame = cap.read()

            # 如果读取失败，跳过本次循环，继续尝试读取下一帧。
            if not ret or frame is None:
                print("警告：读取摄像头画面失败，正在重试...")
                continue

            # 在窗口中显示当前帧。
            cv2.imshow(window_name, frame)

            # waitKey(1) 等待 1 毫秒，同时让 OpenCV 窗口刷新。
            # 如果不调用 waitKey，窗口可能不会正常更新。
            key = cv2.waitKey(1) & 0xFF

            # 按 q 或 Esc 退出循环。
            if key == ord("q") or key == 27:
                break

    finally:
        # 释放摄像头资源。
        cap.release()

        # 关闭所有 OpenCV 创建的窗口。
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

