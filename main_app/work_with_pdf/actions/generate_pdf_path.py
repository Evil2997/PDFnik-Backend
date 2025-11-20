import hashlib
import pathlib
import time

from main_app.main_constants import OUTPUT_DIR


def generate_pdf_path(chat_id: int) -> pathlib.Path:
    # база для хеша: chat_id + текущие миллисекунды
    base = f"{chat_id}_{int(time.time() * 1000)}"
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:6]
    filename = f"{chat_id}_{hash_suffix}.pdf"
    return OUTPUT_DIR / filename
