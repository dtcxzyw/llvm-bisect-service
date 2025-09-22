#!/usr/bin/env python3

import sys
import warnings
import os
import subprocess

warnings.filterwarnings("ignore", category=UserWarning, module="fs")

import fs

STORAGE_DIR = os.getenv("LBS_STORAGE_DIR", "./storage")
def local_provider(commit_id, binary, output) -> bool:
    try:
        storage = fs.open_fs(STORAGE_DIR, writeable=False, create=False)
        file_name = f"{binary}-{commit_id}"
        with open(output, "wb") as out_file:
            storage.download(file_name, out_file)
        os.chmod(output, 0o755)
        return True
    except Exception:
        return False

MANYCLANGS_LOCAL = os.getenv("LBS_MANYCLANGS_LOCAL")
ELFSHAKER_BIN = os.getenv("LBS_ELFSHAKER_BIN")
LLVM_REPO = os.getenv("LBS_LLVM_REPO")

def manyclangs_provider(commit_id, binary, output) -> bool:
    try:
        binary_path = os.path.join(MANYCLANGS_LOCAL, "bin", binary)
        if os.path.exists(binary_path):
            os.remove(binary_path)
        sha = subprocess.check_output(["git", "rev-parse", "--short=10", commit_id], cwd=LLVM_REPO).decode().strip()
        out = subprocess.check_output([ELFSHAKER_BIN, "find", sha], cwd=MANYCLANGS_LOCAL).decode().strip()
        if out == "":
            return False
        snapshot, pack = out.split()
        subprocess.check_call([ELFSHAKER_BIN, "extract", f"{pack}:{snapshot}", "--reset"], cwd=MANYCLANGS_LOCAL)
        env = os.environ.copy()
        env["LINKSCRIPT_LLD"] = "lld"
        env["LINKSCRIPT_CXX"] = "clang++ -target aarch64-linux-gnu"
        env["LINKSCRIPT_CC"] = "clang -target aarch64-linux-gnu"
        subprocess.check_call(["/usr/bin/bash", "link.sh", binary], cwd=MANYCLANGS_LOCAL, env=env)
        with open(output, "w") as f:
            f.write(f"#!/usr/bin/bash\nqemu-aarch64 -L /usr/aarch64-linux-gnu/ {binary_path} \"$@\"\n")
        os.chmod(output, 0o755)
        return True
    except Exception:
        return False

if __name__ == "__main__":
    commit_id = sys.argv[1]
    binary = sys.argv[2]
    output = sys.argv[3]

    if os.path.exists(output):
        os.remove(output)

    if local_provider(commit_id, binary, output):
        exit(0)

    if manyclangs_provider(commit_id, binary, output):
        exit(0)

    exit(1)
