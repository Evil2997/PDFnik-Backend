import hashlib
import pathlib
import time

from main_app.core.constants import TXT_OUTPUT_DIR


def generate_txt_path(chat_id: int) -> pathlib.Path:
    base = f"{chat_id}_{int(time.time() * 1000)}"
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:6]
    filename = f"{chat_id}_{hash_suffix}.txt"
    return TXT_OUTPUT_DIR / filename
