#!/usr/bin/env python3
"""Run realtime YOLO detection through the CUDA-enabled Darknet library."""

import os
import sys


def bootstrap_cuda_runtime():
    root = os.path.dirname(os.path.abspath(__file__))
    cuda_root = os.path.join(root, "cuda_local", "usr", "local", "cuda-10.2")
    cuda_bin = os.path.join(cuda_root, "bin")
    cuda_lib = os.path.join(cuda_root, "lib64")
    tegra_lib = "/usr/lib/aarch64-linux-gnu/tegra"

    if os.environ.get("YOLO_CUDA_BOOTSTRAPPED") == "1":
        return

    env = os.environ.copy()
    env["YOLO_CUDA_BOOTSTRAPPED"] = "1"
    if os.path.isdir(cuda_bin):
        env["PATH"] = os.pathsep.join([cuda_bin] + ([env["PATH"]] if env.get("PATH") else []))
    libs = [p for p in (cuda_lib, tegra_lib) if os.path.isdir(p)]
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        libs + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else [])
    )
    os.execvpe(sys.executable, [sys.executable] + sys.argv, env)


def inject_gpu_library_argument():
    root = os.path.dirname(os.path.abspath(__file__))
    gpu_lib = os.path.join(root, "third_party", "darknet-gpu", "libdarknet.so")
    if "--lib" not in sys.argv:
        sys.argv.extend(["--lib", gpu_lib])


bootstrap_cuda_runtime()
inject_gpu_library_argument()

from yolo_realtime import main


if __name__ == "__main__":
    main()
