"""JSON AST output for tooling; supports explicit Null literal serialization."""
from dataclasses import fields, is_dataclass
import json

from .parser import parse_program
from .values import NULL


def _serialize(value):
    if value is NULL:
        return None
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    return value


def dump_program(program) -> str:
    return json.dumps(_serialize(program), indent=2, ensure_ascii=False, allow_nan=False)


def dump_ast(source: str) -> str:
    return dump_program(parse_program(source))
