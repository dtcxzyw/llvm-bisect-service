import os
import sys
import subprocess

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
bad_commit = (
    subprocess.check_output(["git", "rev-parse", "origin/HEAD"], cwd=llvm_dir)
    .decode()
    .strip()
)
good_commit = (
    subprocess.check_output(["git", "rev-parse", bad_commit + "~100000"], cwd=llvm_dir)
    .decode()
    .strip()
)  # ~2 years
subprocess.check_call(["git", "bisect", "reset"], cwd=llvm_dir)
subprocess.check_call(
    ["git", "bisect", "start", "--no-checkout", bad_commit, good_commit], cwd=llvm_dir
)
bisect_runner_file = "work/oracle.sh"
work_dir = os.path.abspath("work")
with open(bisect_runner_file, "w") as f:
    f.write(f"""#!/usr/bin/bash
LBS_CONSUMER={consumer_script}
cd {work_dir}
LBS_COMMIT_SHA=$(git -C {llvm_dir} rev-parse BISECT_HEAD)
{oracle_command}
""")
os.chmod(bisect_runner_file, 0o755)

subprocess.check_call(
    [
        "git",
        "bisect",
        "run",
        bisect_runner_file,
        consumer_script,
    ],
    cwd=llvm_dir,
    timeout=600.0,
)
