"""Recursive-descent parser; this grammar is still experimental."""
from dataclasses import dataclass
from typing import Any

from .errors import SamhusError
from .lexer import Token, lex
from .stdlib import BUILTIN_SIGNATURES


@dataclass(frozen=True)
class Expr:
    kind: str
    token: Token
    value: Any = None
    left: "Expr | None" = None
    right: "Expr | None" = None
    args: tuple["Expr", ...] = ()


@dataclass(frozen=True)
class Stmt:
    kind: str
    token: Token
    name: str = ""
    expr: Expr | None = None
    mutable: bool = False
    then_body: tuple["Stmt", ...] = ()
    else_body: tuple["Stmt", ...] = ()
    declared_type: str | None = None


@dataclass(frozen=True)
class Function:
    name: str
    token: Token
    params: tuple[str, ...]
    body: tuple[Stmt, ...]
    param_types: tuple[str | None, ...] = ()
    return_type: str | None = None


@dataclass(frozen=True)
class Program:
    functions: tuple[Function, ...]


TYPE_NAMES = frozenset({"Int", "String", "Bool", "Unit", "Any"})


PRECEDENCE = {
    "||": 1, "&&": 2, "==": 3, "!=": 3,
    "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5, "*": 6, "/": 6,
}


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

    def parse_type(self) -> str:
        token = self.expect("IDENT")
        if token.text not in TYPE_NAMES:
            raise SamhusError(f"Unknown type {token.text!r}", token.line, token.column)
        return token.text

    def parse_program(self) -> Program:
        functions: list[Function] = []
        names: set[str] = set()
        while self.current.kind != "EOF":
            self.expect("fn")
            name = self.expect("IDENT")
            if name.text in names:
                raise SamhusError(f"Duplicate function {name.text!r}", name.line, name.column)
            if name.text in BUILTIN_SIGNATURES:
                raise SamhusError(f"{name.text!r} is a reserved builtin", name.line, name.column)
            names.add(name.text)
            self.expect("(")
            params: list[str] = []
            param_types: list[str | None] = []
            if self.current.kind != ")":
                while True:
                    param = self.expect("IDENT")
                    if param.text in params:
                        raise SamhusError(f"Duplicate parameter {param.text!r}", param.line, param.column)
                    params.append(param.text)
                    param_types.append(self.parse_type() if self.accept(":") else None)
                    if not self.accept(","):
                        break
            self.expect(")")
            return_type = self.parse_type() if self.accept("->") else None
            body = self.block()
            functions.append(Function(name.text, name, tuple(params), body, tuple(param_types), return_type))
        entry = next((fn for fn in functions if fn.name == "main"), None)
        if entry is None:
            token = self.current
            raise SamhusError("Missing entry point: only 'fn main()' is a valid entry point", token.line, token.column)
        if entry.params:
            raise SamhusError("Entry point 'main' must have zero parameters", entry.token.line, entry.token.column)
        return Program(tuple(functions))

    def parse(self) -> tuple[Stmt, ...]:
        """Legacy helper: validate the entire program and return main's statements."""
        return next(fn.body for fn in self.parse_program().functions if fn.name == "main")

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
            declared_type = self.parse_type() if self.accept(":") else None
            self.expect("=")
            return Stmt("declare", token, name.text, self.expression(), token.kind == "var", declared_type=declared_type)
        if self.accept("if"):
            condition = self.expression()
            then_body = self.block()
            else_body = self.block() if self.accept("else") else ()
            return Stmt("if", token, expr=condition, then_body=then_body, else_body=else_body)
        if self.accept("while"):
            condition = self.expression()
            return Stmt("while", token, expr=condition, then_body=self.block())
        if self.accept("return"):
            return Stmt("return", token, expr=self.expression())
        if token.kind == "IDENT" and self.tokens[self.index + 1].kind == "=":
            self.index += 1
            self.expect("=")
            return Stmt("assign", token, name=token.text, expr=self.expression())
        if token.kind == "IDENT":
            expression = self.expression()
            if expression.kind != "call":
                raise SamhusError("Only function calls may be expression statements", token.line, token.column)
            return Stmt("expr", token, expr=expression)
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
            if self.accept("("):
                arguments: list[Expr] = []
                if self.current.kind != ")":
                    while True:
                        arguments.append(self.expression())
                        if not self.accept(","):
                            break
                self.expect(")")
                left = Expr("call", token, token.text, args=tuple(arguments))
            else:
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
    """Backwards-compatible API: parse all functions, return the main body."""
    return Parser(source).parse()


def parse_program(source: str) -> Program:
    """Return the complete experimental AST with all function declarations."""
    return Parser(source).parse_program()
