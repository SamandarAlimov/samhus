"""Recursive-descent parser, with precedence-climbing for expressions."""
from dataclasses import dataclass
from typing import Any

from .errors import SamhusError
from .lexer import Token, lex


@dataclass(frozen=True)
class Expr:
    kind: str
    token: Token
    value: Any = None
    left: "Expr | None" = None
    right: "Expr | None" = None


@dataclass(frozen=True)
class Stmt:
    kind: str
    token: Token
    name: str = ""
    expr: Expr | None = None
    mutable: bool = False
    then_body: tuple["Stmt", ...] = ()
    else_body: tuple["Stmt", ...] = ()


PRECEDENCE = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, "<=": 4, ">": 4, ">=": 4, "+": 5, "-": 5, "*": 6, "/": 6}


class Parser:
    def __init__(self, source: str):
        self.tokens = lex(source)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def accept(self, kind: str) -> Token | None:
        if self.current.kind == kind:
            result = self.current
            self.index += 1
            return result
        return None

    def expect(self, kind: str) -> Token:
        result = self.accept(kind)
        if result is None:
            token = self.current
            raise SamhusError(f"Expected {kind!r}, found {token.kind!r}", token.line, token.column)
        return result

    def parse(self) -> tuple[Stmt, ...]:
        self.expect("fn")
        name = self.expect("IDENT")
        if name.text != "main":
            raise SamhusError("Prototype supports only 'fn main()'", name.line, name.column)
        self.expect("(")
        self.expect(")")
        body = self.block()
        self.expect("EOF")
        return body

    def block(self) -> tuple[Stmt, ...]:
        self.expect("{")
        result: list[Stmt] = []
        while self.current.kind not in {"}", "EOF"}:
            if self.accept(";"):
                continue
            result.append(self.statement())
            self.accept(";")
        self.expect("}")
        return tuple(result)

    def statement(self) -> Stmt:
        token = self.current
        if self.accept("let") or self.accept("var"):
            name = self.expect("IDENT")
            self.expect("=")
            return Stmt("declare", token, name.text, self.expression(), token.kind == "var")
        if self.accept("if"):
            condition = self.expression()
            then_body = self.block()
            else_body = self.block() if self.accept("else") else ()
            return Stmt("if", token, expr=condition, then_body=then_body, else_body=else_body)
        if token.kind == "IDENT":
            self.index += 1
            if token.text == "println":
                self.expect("(")
                expression = self.expression()
                self.expect(")")
                return Stmt("println", token, expr=expression)
            self.expect("=")
            return Stmt("assign", token, name=token.text, expr=self.expression())
        raise SamhusError(f"Unexpected statement {token.kind!r}", token.line, token.column)

    def expression(self, min_precedence: int = 1) -> Expr:
        token = self.current
        if self.accept("-") or self.accept("!"):
            left = Expr("unary", token, token.kind, right=self.expression(7))
        elif self.accept("NUMBER"):
            left = Expr("literal", token, int(token.text))
        elif self.accept("STRING"):
            left = Expr("literal", token, token.text)
        elif self.accept("true"):
            left = Expr("literal", token, True)
        elif self.accept("false"):
            left = Expr("literal", token, False)
        elif self.accept("IDENT"):
            left = Expr("name", token, token.text)
        elif self.accept("("):
            left = self.expression()
            self.expect(")")
        else:
            raise SamhusError("Expected expression", token.line, token.column)

        while self.current.kind in PRECEDENCE and PRECEDENCE[self.current.kind] >= min_precedence:
            operator = self.current
            self.index += 1
            right = self.expression(PRECEDENCE[operator.kind] + 1)
            left = Expr("binary", operator, operator.kind, left, right)
        return left


def parse(source: str) -> tuple[Stmt, ...]:
    return Parser(source).parse()
