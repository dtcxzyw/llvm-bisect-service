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
bisect_runner_file = "work/oracle.sh"
work_dir = os.path.abspath("work")
oracle_command = """
./opt-exec -passes=verify test.ll >/dev/null 2>&1
if [ $? -ne 0 ]; then
    exit 125
fi
""" + oracle_command
for binary in ["opt", "llc", "lli"]:
    if f"./{binary}-exec" in oracle_command:
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

def is_good_commit(commit: str) -> bool:
    try:
        res = subprocess.run([os.path.abspath(bisect_runner_file), commit], timeout=60, cwd=llvm_dir).returncode
        return res == 1
    except Exception:
        return False

bad_commit = (
    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=llvm_dir)
    .decode()
    .strip()
)
if is_good_commit(bad_commit):
    print("The test is not interesting.")
    exit(1)
good_commit = None
offset = 100
while offset <= 204800:  # ~5 years
    commit_sha = subprocess.check_output(["git", "rev-parse", f"{bad_commit}~{offset}"], cwd=llvm_dir).decode()
    if is_good_commit(commit_sha):
        good_commit = commit_sha
        break
    offset = int(offset * 1.6)
if good_commit is None:
    print("Could not find a good commit.")
    exit(1)
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
    timeout=1200.0,
)
