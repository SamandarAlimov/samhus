"""Samhus experimental language implementation (bootstrap prototype)."""

from .errors import SamhusError
from .parser import parse
from .runtime import run, run_to_string

__version__ = "0.0.1"
__all__ = ["SamhusError", "parse", "run", "run_to_string"]
