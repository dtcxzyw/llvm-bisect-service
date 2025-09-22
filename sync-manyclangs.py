import subprocess
import os

MANGCLANGS_URL = "https://github.com/elfshaker/manyclangs/releases/download/v0.9.0/"
MANYCLANGS_META = MANGCLANGS_URL + "aarch64-ubuntu2004.esi"
MANYCLANGS_LOCAL = "work/manyclangs/elfshaker_data/packs"

os.makedirs(MANYCLANGS_LOCAL, exist_ok=True)
subprocess.check_call(["wget", MANYCLANGS_META], cwd=MANYCLANGS_LOCAL)
with open(os.path.join(MANYCLANGS_LOCAL, "aarch64-ubuntu2004.esi"), "r") as f:
    lines = f.readlines()
    for line in lines:
        line = line.strip()
        if line.endswith(".pack"):
            filename = line[line.rindex("\t") + 1:]
            if not os.path.exists(os.path.join(MANYCLANGS_LOCAL, filename)):
                print(f"Downloading {filename}")
                subprocess.check_call(
                    ["wget", MANGCLANGS_URL + filename], cwd=MANYCLANGS_LOCAL
                )
            if not os.path.exists(os.path.join(MANYCLANGS_LOCAL, filename + ".idx")):
                print(f"Downloading {filename}.idx")
                subprocess.check_call(
                    ["wget", MANGCLANGS_URL + filename + ".idx"], cwd=MANYCLANGS_LOCAL
                )
print("All done!")
