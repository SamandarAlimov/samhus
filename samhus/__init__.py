"""Samhus experimental language implementation (bootstrap prototype)."""

from .errors import SamhusError
from .parser import parse, parse_program
from .runtime import run, run_to_string

__version__ = "0.0.4"
__all__ = ["SamhusError", "parse", "parse_program", "run", "run_to_string"]
