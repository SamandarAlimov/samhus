"""Experimental Samhus interpreter; this is NOT a sandbox or production compiler."""
from dataclasses import dataclass
from io import StringIO
from typing import TextIO
import sys

from .errors import SamhusError
from .lexer import Token
from .parser import Expr, Function, Program, Stmt, parse_program


Value = int | str | bool | None


@dataclass
class Binding:
    value: Value
    mutable: bool


class _ReturnSignal(Exception):
    def __init__(self, value: Value):
        self.value = value


class Interpreter:
    def __init__(self, output: TextIO, *, max_steps: int = 100_000, max_calls: int = 128):
        if max_steps < 1 or max_calls < 1:
            raise ValueError("Execution limits must be positive")
        self.output = output
        self.scopes: list[dict[str, Binding]] = [{}]
        self.functions: dict[str, Function] = {}
        self.max_steps = max_steps
        self.max_calls = max_calls
        self.steps = 0
        self.call_depth = 0

    def error(self, node: Expr | Stmt | Token, message: str) -> None:
        token = node if isinstance(node, Token) else node.token
        raise SamhusError(message, token.line, token.column)

    def tick(self, node: Expr | Stmt | Token) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            self.error(node, f"Execution step limit exceeded ({self.max_steps})")

    def lookup(self, name: str, node: Expr | Stmt) -> Binding:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        self.error(node, f"Undefined variable {name!r}")
        raise AssertionError("unreachable")

    def invoke(self, name: str, args: tuple[Value, ...], token: Token) -> Value:
        self.tick(token)
        if name == "println":
            if len(args) != 1:
                self.error(token, f"println expects 1 argument, got {len(args)}")
            value = args[0]
            print(str(value).lower() if type(value) is bool else value, file=self.output)
            return None
        function = self.functions.get(name)
        if function is None:
            self.error(token, f"Undefined function {name!r}")
        if len(args) != len(function.params):
            self.error(token, f"Function {name!r} expects {len(function.params)} arguments, got {len(args)}")
        if self.call_depth >= self.max_calls:
            self.error(token, f"Function call depth limit exceeded ({self.max_calls})")
        previous_scopes = self.scopes
        self.scopes = [
            {key: Binding(value, False) for key, value in zip(function.params, args)}
        ]
        self.call_depth += 1
        try:
            try:
                self.execute(function.body)
            except _ReturnSignal as signal:
                return signal.value
            return None
        finally:
            self.call_depth -= 1
            self.scopes = previous_scopes

    def evaluate(self, expr: Expr) -> Value:
        if expr.kind == "literal":
            return expr.value
        if expr.kind == "name":
            return self.lookup(expr.value, expr).value
        if expr.kind == "call":
            args = tuple(self.evaluate(argument) for argument in expr.args)
            return self.invoke(expr.value, args, expr.token)
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
                self.tick(stmt)
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
                elif stmt.kind == "expr":
                    self.evaluate(stmt.expr)
                elif stmt.kind == "return":
                    raise _ReturnSignal(self.evaluate(stmt.expr))
                elif stmt.kind == "if":
                    condition = self.evaluate(stmt.expr)
                    if type(condition) is not bool:
                        self.error(stmt, "If condition must be a boolean")
                    self.execute(stmt.then_body if condition else stmt.else_body, scoped=True)
                elif stmt.kind == "while":
                    while True:
                        self.tick(stmt)  # Also limits loops with an empty body.
                        condition = self.evaluate(stmt.expr)
                        if type(condition) is not bool:
                            self.error(stmt, "While condition must be a boolean")
                        if not condition:
                            break
                        self.execute(stmt.then_body, scoped=True)
                else:
                    self.error(stmt, "Unsupported statement")
        finally:
            if scoped:
                self.scopes.pop()

    def run(self, program: Program) -> None:
        self.functions = {function.name: function for function in program.functions}
        self.invoke("main", (), next(fn.token for fn in program.functions if fn.name == "main"))


def run(source: str, output: TextIO | None = None, *, max_steps: int = 100_000) -> None:
    Interpreter(output if output is not None else sys.stdout, max_steps=max_steps).run(parse_program(source))


def run_to_string(source: str, *, max_steps: int = 100_000) -> str:
    output = StringIO()
    run(source, output, max_steps=max_steps)
    return output.getvalue()
