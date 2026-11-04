"""User-facing diagnostics with source positions."""


class SamhusError(Exception):
    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{line}:{column}: {message}")
