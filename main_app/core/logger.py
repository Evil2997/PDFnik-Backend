import logging

SERVICE_NAME = "backend"

_root_configured = False


def _configure_root_logger() -> None:
    global _root_configured
    if _root_configured:
        return
    _root_configured = True

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
    root.addHandler(handler)


def get_logger(name: str | None = None) -> logging.Logger:
    _configure_root_logger()

    logger_name = name or SERVICE_NAME
    logger = logging.getLogger(logger_name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = get_logger()
