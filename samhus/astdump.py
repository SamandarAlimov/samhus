"""Simple JSON AST inspection for tooling and debugging (experimental)."""
from dataclasses import asdict
import json

from .parser import parse_program


def dump_ast(source: str) -> str:
    return json.dumps(asdict(parse_program(source)), indent=2, ensure_ascii=False)
