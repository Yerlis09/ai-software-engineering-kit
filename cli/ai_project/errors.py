"""Error types and exit codes shared by all commands."""

from __future__ import annotations

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


class KitError(Exception):
    """An expected, user-facing error. The CLI prints the message without a traceback."""

    def __init__(self, message: str, exit_code: int = EXIT_FAILURE) -> None:
        super().__init__(message)
        self.exit_code = exit_code
