import sys
import warnings
import os

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

if __name__ == "__main__":
    commit_id = sys.argv[1]
    binary = sys.argv[2]
    output = sys.argv[3]

    if local_provider(commit_id, binary, output):
        exit(0)

    exit(1)
