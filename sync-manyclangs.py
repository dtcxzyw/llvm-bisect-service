#!/usr/bin/env python3

import os
import subprocess
import sys

MANYCLANGS_ESI_URL = "https://github.com/elfshaker/manyclangs/releases/download/v0.9.0/aarch64-ubuntu2004.esi"
REMOTE_NAME = "manyclangs"


def main() -> int:
    manyclangs_local = os.getenv("LBS_MANYCLANGS_LOCAL")
    if not manyclangs_local:
        print("Error: LBS_MANYCLANGS_LOCAL is not set.", file=sys.stderr)
        return 1
    elfshaker = os.getenv("LBS_ELFSHAKER_BIN", "elfshaker")

    remotes_dir = os.path.join(manyclangs_local, "elfshaker_data", "remotes")
    os.makedirs(remotes_dir, exist_ok=True)
    remote_path = os.path.join(remotes_dir, REMOTE_NAME + ".esi")
    if not os.path.exists(remote_path):
        with open(remote_path, "w") as f:
            f.write(f"meta\tv1\nurl\t{MANYCLANGS_ESI_URL}\n")

    subprocess.check_call([elfshaker, "update"], cwd=manyclangs_local)
    print("All done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
