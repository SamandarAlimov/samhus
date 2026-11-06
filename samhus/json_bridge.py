"""Strict experimental JSON bridge into Samhus immutable Map/List values.

No Float type exists in this prototype, so fractional JSON numbers are
rejected, rather than silently converted into imprecise values. JSON null
currently maps to Unit (None) solely for this experimental bridge.
"""
import json
from typing import Any

from .errors import SamhusError
from .lexer import Token
from .values import MAX_LIST_ITEMS, MAX_MAP_ITEMS, MapValue, map_value

MAX_JSON_BYTES = 1_000_000
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 100_000


def _invalid_constant(value: str) -> None:
    raise ValueError("nonstandard numeric constant " + value)


def _reject_float(value: str) -> None:
    raise ValueError("fractional JSON numbers require Float (not implemented)")


def decode_json(source: str, token: Token) -> Any:
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError:
        raise SamhusError("Invalid JSON: unpaired Unicode surrogate", token.line, token.column) from None
    if size > MAX_JSON_BYTES:
        raise SamhusError("JSON input exceeds byte limit", token.line, token.column)
    def object_pairs(pairs: list[tuple[str, Any]]) -> MapValue:
        return map_value(tuple(pairs), token)
    try:
        raw = json.loads(
            source, object_pairs_hook=object_pairs,
            parse_float=_reject_float, parse_constant=_invalid_constant,
        )
        # Lists decoded by json.loads are Python lists (not Samhus tuples).
        def freeze(value: Any, depth: int, count: list[int]) -> Any:
            count[0] += 1
            if depth > MAX_JSON_DEPTH or count[0] > MAX_JSON_NODES:
                raise SamhusError("JSON structure exceeds resource limits", token.line, token.column)
            if type(value) is list:
                if len(value) > MAX_LIST_ITEMS:
                    raise SamhusError("JSON array exceeds List size limit", token.line, token.column)
                return tuple(freeze(x, depth + 1, count) for x in value)
            if type(value) is MapValue:
                if len(value.entries) > MAX_MAP_ITEMS:
                    raise SamhusError("JSON object exceeds Map size limit", token.line, token.column)
                return MapValue(tuple((freeze(k, depth + 1, count), freeze(v, depth + 1, count))
                                      for k, v in value.entries))
            if type(value) is str:
                try:
                    value.encode("utf-8")
                except UnicodeEncodeError:
                    raise SamhusError("Invalid JSON: unpaired Unicode surrogate", token.line, token.column) from None
            return value
        return freeze(raw, 0, [0])
    except (ValueError, RecursionError) as error:
        raise SamhusError("Invalid JSON: " + str(error), token.line, token.column) from None


def encode_json(value: Any, token: Token) -> str:
    counter = [0]
    def convert(item: Any, depth: int) -> Any:
        counter[0] += 1
        if depth > MAX_JSON_DEPTH or counter[0] > MAX_JSON_NODES:
            raise SamhusError("JSON structure exceeds resource limits", token.line, token.column)
        if type(item) is tuple:
            return [convert(x, depth + 1) for x in item]
        if type(item) is MapValue:
            return {convert(key, depth + 1): convert(val, depth + 1) for key, val in item.entries}
        if type(item) is str:
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                raise SamhusError("JSON serialization: unpaired Unicode surrogate", token.line, token.column) from None
            return item
        if item is None or type(item) in (int, bool):
            return item
        raise SamhusError("Value is not JSON serializable", token.line, token.column)
    try:
        result = json.dumps(convert(value, 0), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(result.encode("utf-8")) > MAX_JSON_BYTES:
            raise SamhusError("JSON output exceeds byte limit", token.line, token.column)
        return result
    except (ValueError, OverflowError, RecursionError, UnicodeEncodeError):
        raise SamhusError("JSON serialization failed", token.line, token.column) from None
