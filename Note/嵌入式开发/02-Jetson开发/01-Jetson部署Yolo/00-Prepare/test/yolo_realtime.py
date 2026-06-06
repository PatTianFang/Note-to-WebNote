#!/usr/bin/env python3
"""Realtime YOLOv3-tiny camera detection using Darknet and OpenCV."""

import argparse
import ctypes
import os
import sys
import time


def bootstrap_local_opencv():
    root = os.path.dirname(os.path.abspath(__file__))
    local_root = os.path.join(root, "opencv_local")
    local_python = os.path.join(local_root, "usr", "lib", "python3", "dist-packages")
    local_libs = [
        os.path.join(local_root, "usr", "lib", "aarch64-linux-gnu"),
        os.path.join(local_root, "usr", "lib"),
    ]

    if not os.path.isdir(local_python):
        return
    if os.environ.get("YOLO_REALTIME_BOOTSTRAPPED") == "1":
        return

    env = os.environ.copy()
    env["YOLO_REALTIME_BOOTSTRAPPED"] = "1"
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
    import numpy as np
except Exception as exc:
    print("Failed to import OpenCV/numpy: {}".format(exc), file=sys.stderr)
    sys.exit(2)


class BOX(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("w", ctypes.c_float),
        ("h", ctypes.c_float),
    ]


class DETECTION(ctypes.Structure):
    _fields_ = [
        ("bbox", BOX),
        ("classes", ctypes.c_int),
        ("prob", ctypes.POINTER(ctypes.c_float)),
        ("mask", ctypes.POINTER(ctypes.c_float)),
        ("objectness", ctypes.c_float),
        ("sort_class", ctypes.c_int),
    ]


class IMAGE(ctypes.Structure):
    _fields_ = [
        ("w", ctypes.c_int),
        ("h", ctypes.c_int),
        ("c", ctypes.c_int),
        ("data", ctypes.POINTER(ctypes.c_float)),
    ]


def parse_device(value):
    return int(value) if value.isdigit() else value


def require_file(path, label):
    if not os.path.isfile(path):
        raise RuntimeError("{} not found: {}".format(label, path))
    return path


def load_names(path):
    with open(path, "r") as fh:
        return [line.strip() for line in fh if line.strip()]


class DarknetYOLO(object):
    def __init__(self, lib_path, cfg_path, weights_path, names_path, thresh, nms):
        self.lib_path = require_file(lib_path, "Darknet library")
        self.cfg_path = require_file(cfg_path, "YOLO cfg")
        self.weights_path = require_file(weights_path, "YOLO weights")
        self.names = load_names(require_file(names_path, "class names"))
        self.thresh = float(thresh)
        self.nms = float(nms)

        self.lib = ctypes.CDLL(self.lib_path, mode=ctypes.RTLD_GLOBAL)
        self._configure_api()
        self.net = self.lib.load_network(
            self.cfg_path.encode("utf-8"), self.weights_path.encode("utf-8"), 0
        )
        if not self.net:
            raise RuntimeError("Darknet failed to load network")
        self.net_w = self.lib.network_width(self.net)
        self.net_h = self.lib.network_height(self.net)

    def _configure_api(self):
        self.lib.load_network.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        self.lib.load_network.restype = ctypes.c_void_p
        self.lib.network_width.argtypes = [ctypes.c_void_p]
        self.lib.network_width.restype = ctypes.c_int
        self.lib.network_height.argtypes = [ctypes.c_void_p]
        self.lib.network_height.restype = ctypes.c_int
        self.lib.network_predict_image.argtypes = [ctypes.c_void_p, IMAGE]
        self.lib.network_predict_image.restype = ctypes.POINTER(ctypes.c_float)
        self.lib.get_network_boxes.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        self.lib.get_network_boxes.restype = ctypes.POINTER(DETECTION)
        self.lib.do_nms_obj.argtypes = [
            ctypes.POINTER(DETECTION),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_float,
        ]
        self.lib.free_detections.argtypes = [ctypes.POINTER(DETECTION), ctypes.c_int]

    def _frame_to_image(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.net_w, self.net_h))
        chw = resized.transpose(2, 0, 1).astype(np.float32) / 255.0
        chw = np.ascontiguousarray(chw)
        image = IMAGE(
            self.net_w,
            self.net_h,
            3,
            chw.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )
        return image, chw

    def detect(self, frame):
        image, _buffer = self._frame_to_image(frame)
        self.lib.network_predict_image(self.net, image)

        count = ctypes.c_int(0)
        detections = self.lib.get_network_boxes(
            self.net,
            frame.shape[1],
            frame.shape[0],
            self.thresh,
            0.5,
            None,
            0,
            ctypes.pointer(count),
        )
        num = count.value
        if self.nms > 0:
            self.lib.do_nms_obj(detections, num, len(self.names), self.nms)

        results = []
        try:
            for i in range(num):
                det = detections[i]
                for class_id in range(len(self.names)):
                    confidence = det.prob[class_id]
                    if confidence <= self.thresh:
                        continue
                    box = det.bbox
                    left = int(box.x - box.w / 2)
                    top = int(box.y - box.h / 2)
                    right = int(box.x + box.w / 2)
                    bottom = int(box.y + box.h / 2)
                    results.append(
                        {
                            "label": self.names[class_id],
                            "confidence": float(confidence),
                            "box": (left, top, right, bottom),
                        }
                    )
        finally:
            if detections:
                self.lib.free_detections(detections, num)
        return results


def open_camera(device, width, height):
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        raise RuntimeError("Cannot open camera device: {}".format(device))
    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def color_for(label):
    seed = sum(ord(ch) for ch in label)
    return (50 + seed * 3 % 205, 50 + seed * 7 % 205, 50 + seed * 11 % 205)


def draw_detections(frame, detections):
    height, width = frame.shape[:2]
    for det in detections:
        left, top, right, bottom = det["box"]
        left = max(0, min(width - 1, left))
        right = max(0, min(width - 1, right))
        top = max(0, min(height - 1, top))
        bottom = max(0, min(height - 1, bottom))
        color = color_for(det["label"])
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        text = "{} {:.0f}%".format(det["label"], det["confidence"] * 100)
        y = top - 8 if top > 18 else top + 18
        cv2.putText(frame, text, (left, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return frame


def default_paths(root):
    return {
        "lib": os.path.join(root, "third_party", "darknet-master", "libdarknet.so"),
        "cfg": os.path.join(root, "models", "yolov3-tiny", "yolov3-tiny.cfg"),
        "weights": os.path.join(root, "models", "yolov3-tiny", "yolov3-tiny.weights"),
        "names": os.path.join(root, "models", "yolov3-tiny", "coco.names"),
    }


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    paths = default_paths(root)
    parser = argparse.ArgumentParser(description="Realtime YOLOv3-tiny camera detection")
    parser.add_argument("--device", default="0", help="camera index or path, default: 0")
    parser.add_argument("--width", type=int, default=640, help="requested camera width")
    parser.add_argument("--height", type=int, default=480, help="requested camera height")
    parser.add_argument("--thresh", type=float, default=0.35, help="detection threshold")
    parser.add_argument("--nms", type=float, default=0.45, help="NMS threshold")
    parser.add_argument("--skip-frames", type=int, default=3, help="run YOLO every N frames")
    parser.add_argument("--window", default="YOLO Realtime Detection", help="window title")
    parser.add_argument("--lib", default=paths["lib"], help="path to libdarknet.so")
    parser.add_argument("--cfg", default=paths["cfg"], help="path to YOLO cfg")
    parser.add_argument("--weights", default=paths["weights"], help="path to YOLO weights")
    parser.add_argument("--names", default=paths["names"], help="path to class names")
    parser.add_argument("--image", default="", help="optional image path for a still-image test")
    parser.add_argument("--test-only", action="store_true", help="process one frame and exit")
    parser.add_argument("--save-frame", default="", help="optional output image path")
    args = parser.parse_args()

    yolo = DarknetYOLO(args.lib, args.cfg, args.weights, args.names, args.thresh, args.nms)
    print(
        "Loaded YOLOv3-tiny {}x{} with {} classes.".format(
            yolo.net_w, yolo.net_h, len(yolo.names)
        ),
        flush=True,
    )

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            raise RuntimeError("Cannot read image: {}".format(args.image))
        detections = yolo.detect(frame)
        output = draw_detections(frame.copy(), detections)
        if args.save_frame:
            if not cv2.imwrite(args.save_frame, output):
                raise RuntimeError("Failed to save frame to {}".format(args.save_frame))
        print(
            "Processed image {}; detections={}.".format(args.image, len(detections)),
            flush=True,
        )
        if args.test_only:
            return
        cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
        cv2.imshow(args.window, output)
        print("Showing YOLO image result. Press q or Esc in the window to exit.", flush=True)
        while True:
            key = cv2.waitKey(20) & 0xFF
            if key in (27, ord("q")):
                break
        cv2.destroyAllWindows()
        return

    cap = open_camera(parse_device(args.device), args.width, args.height)
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("Camera opened, but no frame was read.")

        detections = yolo.detect(frame)
        output = draw_detections(frame.copy(), detections)
        if args.save_frame:
            if not cv2.imwrite(args.save_frame, output):
                raise RuntimeError("Failed to save frame to {}".format(args.save_frame))

        if args.test_only:
            print(
                "Processed one frame from camera {}; detections={}.".format(
                    args.device, len(detections)
                ),
                flush=True,
            )
            return

        cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
        print("Showing YOLO detections. Press q or Esc in the window to exit.", flush=True)
        frame_id = 0
        last_detections = detections
        last_time = time.time()
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Frame read failed; retrying...", flush=True)
                time.sleep(0.1)
                continue
            if frame_id % max(1, args.skip_frames) == 0:
                last_detections = yolo.detect(frame)
            shown = draw_detections(frame.copy(), last_detections)

            now = time.time()
            fps = 1.0 / max(now - last_time, 1e-6)
            last_time = now
            cv2.putText(
                shown,
                "FPS {:.1f}  detections {}".format(fps, len(last_detections)),
                (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
            cv2.imshow(args.window, shown)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            frame_id += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
