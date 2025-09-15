import warnings
import sys
import os
import pathlib
import datetime
import subprocess
import tqdm

warnings.filterwarnings("ignore", category=UserWarning, module="fs")

import fs


WORK_DIR = "./work"
STORAGE_DIR = os.getenv("LBS_STORAGE_DIR", "./storage")
WINDOW_SIZE = int(os.getenv("LBS_WINDOW_SIZE", "30"))
LLVM_DIR = os.path.abspath(os.path.join(WORK_DIR, "llvm-project"))

INTERESTING_DIRS = [
    "llvm/include/llvm/Analysis",
    "llvm/lib/Analysis",
    "llvm/include/llvm/IR",
    "llvm/lib/IR",
    "llvm/include/llvm/Transforms",
    "llvm/lib/Transforms",
    "llvm/include/llvm/CodeGen",
    "llvm/lib/CodeGen",
    "llvm/include/llvm/Target",
    "llvm/lib/Target",
]


def list_required_bins():
    cutoff = datetime.datetime.now() - datetime.timedelta(days=WINDOW_SIZE)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    output = subprocess.check_output(
        [
            "git",
            "-C",
            LLVM_DIR,
            "log",
            "--since=" + cutoff_str,
            "--pretty=format:%H",
            "--reverse",
        ]
    )
    commits = output.decode("utf-8").strip().split("\n")
    tasks = []
    for commit in commits:
        modified_files = (
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    LLVM_DIR,
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    commit,
                ]
            )
            .decode("utf-8")
            .strip()
            .splitlines()
        )
        for file in modified_files:
            if any(file.startswith(prefix) for prefix in INTERESTING_DIRS):
                tasks.append("opt-" + commit)
                tasks.append("llc-" + commit)
                tasks.append("lli-" + commit)
                break
    return tasks


def build_and_upload(name: str) -> str:
    llvm_build_dir = os.path.join(WORK_DIR, "llvm-build")
    os.makedirs(llvm_build_dir, exist_ok=True)
    target, commit = name.split("-")
    subprocess.check_call(
        ["git", "-C", LLVM_DIR, "-c", "advice.detachedHead=false", "checkout", commit]
    )
    try:
        subprocess.check_call(
            [
                "cmake",
                "-S",
                os.path.join(LLVM_DIR, "llvm"),
                "-DCMAKE_BUILD_TYPE=MinSizeRel",
                "-G",
                "Ninja",
                "-DLLVM_PARALLEL_LINK_JOBS=4",
                "-DLLVM_ENABLE_ASSERTIONS=ON",
                "-DLLVM_ABI_BREAKING_CHECKS=WITH_ASSERTS",
                "-DLLVM_ENABLE_WARNINGS=OFF",
                "-DLLVM_APPEND_VC_REV=OFF",
                "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
                "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
            ],
            cwd=llvm_build_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["cmake", "--build", ".", "-j", str(os.cpu_count()), "-t", target],
            cwd=llvm_build_dir,
        )
        bin_path = os.path.join(llvm_build_dir, "bin", target)
        upx_path = os.path.join(WORK_DIR, "upx")
        compressed_path = bin_path + ".upx"
        if os.path.exists(compressed_path):
            os.remove(compressed_path)
        subprocess.check_call(
            [upx_path, "-o", compressed_path, "--lzma", "--best", bin_path]
        )
        return compressed_path
    except subprocess.CalledProcessError:
        dummy_path = os.path.join(WORK_DIR, "dummy")
        pathlib.Path(dummy_path).touch()
        return dummy_path


def producer_iter():
    storage = fs.open_fs(STORAGE_DIR, writeable=True, create=True)
    subprocess.check_call(["git", "-C", LLVM_DIR, "checkout", "main"])
    subprocess.check_call(["git", "-C", LLVM_DIR, "pull", "origin", "main"])
    requested_bins = list_required_bins()
    available_bins = storage.listdir(".")
    tasks = [name for name in requested_bins if name not in available_bins]
    progress = tqdm.tqdm(tasks)
    for name in progress:
        progress.set_description(f"Building {name}")
        src_bin = build_and_upload(name)
        with open(src_bin, "rb") as bin_file:
            storage.upload(name, bin_file)


def main():
    upx_path = os.path.join(WORK_DIR, "upx")
    if not os.path.exists(upx_path):
        print("Error: UPX binary not found in work directory.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(LLVM_DIR):
        print(
            "Error: LLVM project directory not found in work directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    while True:
        try:
            producer_iter()
        except Exception as e:
            print(f"Error in producer_iter: {e}", file=sys.stderr)
            break


if __name__ == "__main__":
    main()
