class CommandFailedError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        super().__init__(f"Command failed (code={returncode}): {' '.join(cmd)}")
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr


class TargetPrepareError(RuntimeError):
    pass


class TranscribeError(RuntimeError):
    pass
