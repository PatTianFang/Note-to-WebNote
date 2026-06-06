#!/usr/bin/env python3
"""Show a live camera preview with OpenCV."""

import argparse
import os
import sys
import time


def bootstrap_local_opencv():
    """Use the locally unpacked OpenCV packages when system cv2 is missing."""
    root = os.path.dirname(os.path.abspath(__file__))
    local_root = os.path.join(root, "opencv_local")
    local_python = os.path.join(local_root, "usr", "lib", "python3", "dist-packages")
    local_libs = [
        os.path.join(local_root, "usr", "lib", "aarch64-linux-gnu"),
        os.path.join(local_root, "usr", "lib"),
    ]

    if not os.path.isdir(local_python):
        return
    if os.environ.get("CAMERA_VIEWER_BOOTSTRAPPED") == "1":
        return

    env = os.environ.copy()
    env["CAMERA_VIEWER_BOOTSTRAPPED"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [local_python] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        [p for p in local_libs if os.path.isdir(p)]
        + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else [])
    )
    os.execvpe(sys.executable, [sys.executable] + sys.argv, env)


bootstrap_local_opencv()

try:
    import cv2
except Exception as exc:
    print("Failed to import OpenCV cv2: {}".format(exc), file=sys.stderr)
    print("Install python3-opencv, or keep opencv_local next to this script.", file=sys.stderr)
    sys.exit(2)


def parse_device(value):
    return int(value) if value.isdigit() else value


def open_camera(device, width, height):
    backend = getattr(cv2, "CAP_V4L2", 200)
    try:
        cap = cv2.VideoCapture(device, backend)
    except TypeError:
        cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        raise RuntimeError("Cannot open camera device: {}".format(device))

    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def read_frame(cap, attempts):
    frame = None
    for _ in range(max(1, attempts)):
        ok, current = cap.read()
        if ok and current is not None:
            frame = current
        time.sleep(0.03)
    if frame is None:
        raise RuntimeError("Camera opened, but no frame was read.")
    return frame


def main():
    parser = argparse.ArgumentParser(description="OpenCV live camera preview")
    parser.add_argument("--device", default="0", help="camera index or path, default: 0")
    parser.add_argument("--width", type=int, default=640, help="requested frame width")
    parser.add_argument("--height", type=int, default=480, help="requested frame height")
    parser.add_argument("--window", default="Camera Preview", help="preview window title")
    parser.add_argument("--test-only", action="store_true", help="read one frame and exit")
    parser.add_argument("--save-frame", default="", help="optional path for a captured frame")
    parser.add_argument("--warmup-frames", type=int, default=10, help="frames to read before use")
    args = parser.parse_args()

    device = parse_device(args.device)
    cap = open_camera(device, args.width, args.height)

    try:
        if args.test_only:
            frame = read_frame(cap, args.warmup_frames)
            if args.save_frame:
                if not cv2.imwrite(args.save_frame, frame):
                    raise RuntimeError("Failed to save frame to {}".format(args.save_frame))
            print(
                "OpenCV {} opened camera {} and read frame {}x{}.".format(
                    cv2.__version__, args.device, frame.shape[1], frame.shape[0]
                ),
                flush=True,
            )
            return

        cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
        print(
            "Showing camera {}. Press q or Esc in the window to exit.".format(args.device),
            flush=True,
        )
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Frame read failed; retrying...", flush=True)
                time.sleep(0.1)
                continue
            cv2.imshow(args.window, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
