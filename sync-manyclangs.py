#!/usr/bin/env python3

import os
import subprocess
import sys

MANYCLANGS_ESI_URL = "https://github.com/elfshaker/manyclangs/releases/download/v0.9.0/aarch64-ubuntu2004.esi"
REMOTE_NAME = "manyclangs"


def elfshaker_output(elfshaker: str, args: list[str], cwd: str) -> list[str]:
    res = subprocess.run(
        [elfshaker, *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if res.returncode != 0:
        return []
    return [line for line in res.stdout.splitlines() if line.strip()]


def fetch_missing_packs(elfshaker: str, manyclangs_local: str) -> int:
    packs_dir = os.path.join(manyclangs_local, "elfshaker_data", "packs")
    fetched = 0
    for pack in elfshaker_output(
        elfshaker, ["list-packs", "--format", "%p"], manyclangs_local
    ):
        if pack.startswith("loose/"):
            continue
        if os.path.exists(os.path.join(packs_dir, pack + ".pack")):
            continue
        snapshots = elfshaker_output(
            elfshaker, ["list", pack, "--format", "%t"], manyclangs_local
        )
        if not snapshots:
            continue
        snapshot = f"{pack}:{snapshots[-1]}"
        files = elfshaker_output(
            elfshaker, ["list-files", snapshot, "--format", "%b %f"], manyclangs_local
        )
        if not files:
            continue
        _, path = min(
            files, key=lambda line: int(line.split(maxsplit=1)[0])
        ).split(maxsplit=1)
        print(f"Fetching {pack}.pack via elfshaker lazy load...")
        with open(os.devnull, "wb") as devnull:
            subprocess.check_call(
                [elfshaker, "show", snapshot, path],
                cwd=manyclangs_local,
                stdout=devnull,
            )
        fetched += 1
    return fetched


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
    fetched = fetch_missing_packs(elfshaker, manyclangs_local)
    print(f"All done! Fetched {fetched} missing pack(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
