"""Experimental interpreter; intentionally not a production compiler."""
from dataclasses import dataclass
from io import StringIO
from typing import TextIO
import sys

from .errors import SamhusError
from .parser import Expr, Stmt, parse


Value = int | str | bool


@dataclass
class Binding:
    value: Value
    mutable: bool


class Interpreter:
    def __init__(self, output: TextIO):
        self.output = output
        self.scopes: list[dict[str, Binding]] = [{}]

    def error(self, expr: Expr | Stmt, message: str) -> None:
        raise SamhusError(message, expr.token.line, expr.token.column)

    def lookup(self, name: str, expr: Expr | Stmt) -> Binding:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        self.error(expr, f"Undefined variable {name!r}")
        raise AssertionError("unreachable")

    def evaluate(self, expr: Expr) -> Value:
        if expr.kind == "literal":
            return expr.value
        if expr.kind == "name":
            return self.lookup(expr.value, expr).value
        if expr.kind == "unary":
            right = self.evaluate(expr.right)
            if expr.value == "!":
                if type(right) is not bool:
                    self.error(expr, "'!' requires a boolean")
                return not right
            if type(right) is not int:
                self.error(expr, "Unary '-' requires an integer")
            return -right
        if expr.kind == "binary":
            left = self.evaluate(expr.left)
            operator = expr.value
            if operator in {"&&", "||"}:
                if type(left) is not bool:
                    self.error(expr, f"'{operator}' requires booleans")
                if operator == "&&" and not left:
                    return False
                if operator == "||" and left:
                    return True
                right = self.evaluate(expr.right)
                if type(right) is not bool:
                    self.error(expr, f"'{operator}' requires booleans")
                return right
            right = self.evaluate(expr.right)
            if operator in {"==", "!="}:
                equals = type(left) is type(right) and left == right
                return equals if operator == "==" else not equals
            if operator == "+" and type(left) is str and type(right) is str:
                return left + right
            if type(left) is not int or type(right) is not int:
                self.error(expr, f"'{operator}' requires integers (or two strings for '+')")
            if operator == "+":
                return left + right
            if operator == "-":
                return left - right
            if operator == "*":
                return left * right
            if operator == "/":
                if right == 0:
                    self.error(expr, "Division by zero")
                # Integer division truncates toward zero without float conversion.
                quotient = abs(left) // abs(right)
                return -quotient if (left < 0) != (right < 0) else quotient
            if operator == "<":
                return left < right
            if operator == "<=":
                return left <= right
            if operator == ">":
                return left > right
            if operator == ">=":
                return left >= right
        self.error(expr, "Unsupported expression")
        raise AssertionError("unreachable")

    def execute(self, statements: tuple[Stmt, ...], scoped: bool = False) -> None:
        if scoped:
            self.scopes.append({})
        try:
            for stmt in statements:
                if stmt.kind == "declare":
                    scope = self.scopes[-1]
                    if stmt.name in scope:
                        self.error(stmt, f"Variable {stmt.name!r} already declared")
                    scope[stmt.name] = Binding(self.evaluate(stmt.expr), stmt.mutable)
                elif stmt.kind == "assign":
                    binding = self.lookup(stmt.name, stmt)
                    if not binding.mutable:
                        self.error(stmt, f"Cannot assign to immutable variable {stmt.name!r}")
                    binding.value = self.evaluate(stmt.expr)
                elif stmt.kind == "println":
                    value = self.evaluate(stmt.expr)
                    print(str(value).lower() if type(value) is bool else value, file=self.output)
                elif stmt.kind == "if":
                    condition = self.evaluate(stmt.expr)
                    if type(condition) is not bool:
                        self.error(stmt, "If condition must be a boolean")
                    self.execute(stmt.then_body if condition else stmt.else_body, scoped=True)
                else:
                    self.error(stmt, "Unsupported statement")
        finally:
            if scoped:
                self.scopes.pop()


def run(source: str, output: TextIO | None = None) -> None:
    program = parse(source)
    Interpreter(output if output is not None else sys.stdout).execute(program)


def run_to_string(source: str) -> str:
    output = StringIO()
    run(source, output)
    return output.getvalue()
