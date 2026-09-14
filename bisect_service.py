import calendar
import datetime
import os
import subprocess
from typing import Optional

os.makedirs("work", exist_ok=True)
command_string = os.getenv("LBS_COMMAND_STRING")
pos1 = command_string.index("```\n")
pos2 = command_string.index("```\n", pos1 + 4)
oracle_command = command_string[pos1 + 4 : pos2]
pos3 = command_string.index("```\n", pos2 + 4)
pos4 = command_string.index("```", pos3 + 4)
input_string = command_string[pos3 + 4 : pos4]
input_file_path = "work/test.ll"
with open(input_file_path, "w") as f:
    f.write(input_string)
llvm_dir = os.getenv("LBS_LLVM_REPO")
consumer_script = os.path.dirname(os.path.abspath(__file__)) + "/consumer.py"
anchors_file = os.getenv("LBS_ANCHORS_FILE", os.path.dirname(os.path.abspath(__file__)) + "/anchors.txt")
bisect_runner_file = "work/oracle.sh"
work_dir = os.path.abspath("work")
MAX_MONTHS = 60  # ~5 years
MAX_CONSUME_ATTEMPTS = 10
oracle_command = """
./opt-exec -passes=verify test.ll >/dev/null 2>&1
if [ $? -ne 0 ]; then
    exit 125
fi
""" + oracle_command
required_binaries = [binary for binary in ["opt", "llc", "lli"] if f"./{binary}-exec" in oracle_command]
for binary in required_binaries:
    oracle_command = f"""{consumer_script} $LBS_COMMIT_SHA {binary} {binary}-exec
if [ $? -ne 0 ]; then
    exit 125
fi
""" + oracle_command

with open(bisect_runner_file, "w") as f:
    f.write(f"""#!/usr/bin/bash
cd {work_dir}
if [ $# -eq 1 ]; then
LBS_COMMIT_SHA="$1"
else
LBS_COMMIT_SHA=$(git -C {llvm_dir} rev-parse BISECT_HEAD)
fi
echo "[llvm-bisect-service] Running on commit $LBS_COMMIT_SHA"
{oracle_command}
""")
os.chmod(bisect_runner_file, 0o755)

def can_consume(commit: str) -> bool:
    for binary in required_binaries:
        try:
            res = subprocess.run(
                [consumer_script, commit, binary, binary + "-exec"],
                timeout=60,
                cwd=work_dir,
            )
        except Exception:
            return False
        if res.returncode != 0:
            return False
    return True


def is_good_commit(commit: str) -> bool:
    try:
        res = subprocess.run([os.path.abspath(bisect_runner_file), commit], timeout=60, cwd=llvm_dir).returncode
        return res == 0
    except Exception:
        return False


def get_commit_before(timestamp: int) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-list", "-1", f"--before={timestamp}", bad_commit],
            cwd=llvm_dir,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except subprocess.CalledProcessError:
        return ""


def get_parent(commit: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", f"{commit}^"],
            cwd=llvm_dir,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except subprocess.CalledProcessError:
        return ""


def months_before(dt: datetime.datetime, months: int) -> datetime.datetime:
    month_index = dt.year * 12 + (dt.month - 1) - months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


bad_commit = (
    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=llvm_dir)
    .decode()
    .strip()
)
if is_good_commit(bad_commit):
    print("The test is not interesting.", flush=True)
    exit(1)
bad_time = datetime.datetime.fromtimestamp(
    int(
        subprocess.check_output(["git", "show", "-s", "--format=%ct", bad_commit], cwd=llvm_dir)
        .decode()
        .strip()
    ),
    datetime.timezone.utc,
)


def load_anchors() -> list[tuple[str, str]]:
    anchors = []
    try:
        with open(anchors_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) == 2:
                    anchors.append((parts[0], parts[1]))
    except FileNotFoundError:
        pass
    anchors.sort()
    return anchors


def candidate_commits():
    anchors = load_anchors()
    if anchors:
        for month, commit in reversed(anchors):
            yield f"anchor {month}", commit
        return
    print("[llvm-bisect-service] Anchor list is empty; falling back to on-the-fly search.", flush=True)
    for months_back in range(1, MAX_MONTHS + 1):
        candidate = get_commit_before(int(months_before(bad_time, months_back).timestamp()))
        attempts = 0
        while candidate and attempts < MAX_CONSUME_ATTEMPTS:
            if can_consume(candidate):
                break
            candidate = get_parent(candidate)
            attempts += 1
        if not candidate:
            return
        yield f"~{months_back} month(s) back", candidate


good_commit = None
for label, candidate in candidate_commits():
    if candidate == bad_commit:
        continue
    print(f"[llvm-bisect-service] Trying {label}: {candidate}", flush=True)
    if is_good_commit(candidate):
        good_commit = candidate
        break
if good_commit is None:
    print("Could not find a good commit.", flush=True)
    exit(1)
print(f"Bad commit: {bad_commit} Good commit: {good_commit}", flush=True)
subprocess.check_call(["git", "bisect", "reset"], cwd=llvm_dir)
subprocess.check_call(
    ["git", "bisect", "start", "--no-checkout", bad_commit, good_commit], cwd=llvm_dir
)
subprocess.check_call(
    [
        "git",
        "bisect",
        "run",
        os.path.abspath(bisect_runner_file)
    ],
    cwd=llvm_dir,
    timeout=1800.0,
)
