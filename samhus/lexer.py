"""Small, deterministic lexer for the experimental Samhus grammar."""
from dataclasses import dataclass

from .errors import SamhusError


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    column: int


KEYWORDS = {"fn", "let", "var", "if", "else", "while", "return", "true", "false", "null", "import"}
TWO_CHAR = {"==", "!=", "<=", ">=", "&&", "||", "->"}
ONE_CHAR = set("+-*/=(){}[];!<>,:")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


# Prototype resource guards. These are not a secure sandbox or final limits.
MAX_SOURCE_CHARS = 1_000_000
MAX_TOKENS = 250_000
MAX_NUMBER_CHARS = 4_096
MAX_STRING_CHARS = 100_000


def lex(source: str) -> list[Token]:
    if len(source) > MAX_SOURCE_CHARS:
        raise SamhusError(f"Source size limit exceeded ({MAX_SOURCE_CHARS} characters)", 1, 1)
    tokens: list[Token] = []
    index, line, column = 0, 1, 1

    def step() -> str:
        nonlocal index, line, column
        character = source[index]
        index += 1
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1
        return character

    while index < len(source):
        if len(tokens) >= MAX_TOKENS:
            raise SamhusError(f"Token count limit exceeded ({MAX_TOKENS})", line, column)
        char = source[index]
        if char.isspace():
            step()
            continue
        if source.startswith("//", index):
            while index < len(source) and source[index] != "\n":
                step()
            continue
        start_line, start_column = line, column
        if char.isascii() and (char.isalpha() or char == "_"):
            value = ""
            while index < len(source) and source[index].isascii() and (source[index].isalnum() or source[index] == "_"):
                value += step()
            tokens.append(Token(value if value in KEYWORDS else "IDENT", value, start_line, start_column))
            continue
        if char.isascii() and char.isdigit():
            value = ""
            while index < len(source) and source[index].isascii() and source[index].isdigit():
                value += step()
            fractional = False
            if index < len(source) and source[index] == ".":
                if index + 1 >= len(source) or not source[index + 1].isascii() or not source[index + 1].isdigit():
                    raise SamhusError("Float literal requires digits after decimal point", line, column)
                fractional = True
                value += step()
                while index < len(source) and source[index].isascii() and source[index].isdigit():
                    value += step()
            if index < len(source) and source[index] in "eE":
                fractional = True
                value += step()
                if index < len(source) and source[index] in "+-":
                    value += step()
                if index >= len(source) or not source[index].isascii() or not source[index].isdigit():
                    raise SamhusError("Float exponent requires digits", line, column)
                while index < len(source) and source[index].isascii() and source[index].isdigit():
                    value += step()
            if len(value) > MAX_NUMBER_CHARS:
                raise SamhusError(f"Numeric literal length limit exceeded ({MAX_NUMBER_CHARS})", start_line, start_column)
            tokens.append(Token("FLOAT" if fractional else "NUMBER", value, start_line, start_column))
            continue
        if char == '"':
            step()
            value = ""
            while index < len(source) and source[index] != '"':
                if source[index] == "\\":
                    step()
                    if index >= len(source) or source[index] not in ESCAPES:
                        raise SamhusError("Invalid string escape", line, column)
                    value += ESCAPES[step()]
                elif source[index] == "\n":
                    raise SamhusError("Unterminated string literal", start_line, start_column)
                else:
                    value += step()
            if index >= len(source):
                raise SamhusError("Unterminated string literal", start_line, start_column)
            step()
            if len(value) > MAX_STRING_CHARS:
                raise SamhusError(f"String literal length limit exceeded ({MAX_STRING_CHARS})", start_line, start_column)
            tokens.append(Token("STRING", value, start_line, start_column))
            continue
        pair = source[index:index + 2]
        if pair in TWO_CHAR:
            step()
            step()
            tokens.append(Token(pair, pair, start_line, start_column))
            continue
        if char in ONE_CHAR:
            step()
            tokens.append(Token(char, char, start_line, start_column))
            continue
        raise SamhusError(f"Unexpected character {char!r}", line, column)
    tokens.append(Token("EOF", "", line, column))
    return tokens
