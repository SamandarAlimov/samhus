"""Small, deterministic lexer for the experimental Samhus grammar."""
from dataclasses import dataclass

from .errors import SamhusError


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    column: int


KEYWORDS = {"fn", "let", "var", "if", "else", "while", "return", "true", "false"}
TWO_CHAR = {"==", "!=", "<=", ">=", "&&", "||", "->"}
ONE_CHAR = set("+-*/=(){}[];!<>,:")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def lex(source: str) -> list[Token]:
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
            tokens.append(Token("NUMBER", value, start_line, start_column))
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
