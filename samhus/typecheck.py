"""Opt-in, conservative prototype static type checker for Samhus.

Unannotated parameters and function returns are Any. Typed declarations and
known literal expressions are checked; Any permits dynamic checks at runtime.
This is an experimental analyzer, not a soundness proof.
"""
from dataclasses import dataclass

from .errors import SamhusError
from .parser import Expr, Function, Program, Stmt, parse_program
from .stdlib import BUILTIN_SIGNATURES

Type = str
ANY = "Any"
UNIT = "Unit"


@dataclass(frozen=True)
class Symbol:
    type_name: Type
    mutable: bool


class TypeChecker:
    def __init__(self, program: Program):
        self.functions: dict[str, Function] = {fn.name: fn for fn in program.functions}
        self.scopes: list[dict[str, Symbol]] = []
        self.current_function: Function | None = None

    def fail(self, node: Expr | Stmt, message: str) -> None:
        raise SamhusError(message, node.token.line, node.token.column)

    def resolve(self, name: str, node: Expr | Stmt) -> Symbol:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        self.fail(node, f"Undefined variable {name!r}")
        raise AssertionError("unreachable")

    @staticmethod
    def compatible(actual: Type, expected: Type) -> bool:
        return ANY in {actual, expected} or actual == expected

    def require(self, actual: Type, expected: Type, node: Expr | Stmt) -> None:
        if not self.compatible(actual, expected):
            self.fail(node, f"Type mismatch: expected {expected}, got {actual}")

    def expr_type(self, expr: Expr) -> Type:
        if expr.kind == "literal":
            if type(expr.value) is bool:
                return "Bool"
            if type(expr.value) is int:
                return "Int"
            if type(expr.value) is str:
                return "String"
            self.fail(expr, "Unsupported literal type")
        if expr.kind == "name":
            return self.resolve(expr.value, expr).type_name
        if expr.kind == "call":
            signature = BUILTIN_SIGNATURES.get(expr.value)
            if signature is not None:
                params, return_type = signature
                if len(expr.args) != len(params):
                    self.fail(expr, f"{expr.value} expects {len(params)} argument, got {len(expr.args)}")
                for argument, expected in zip(expr.args, params):
                    actual = self.expr_type(argument)
                    if expected != ANY:
                        self.require(actual, expected, argument)
                return return_type
            function = self.functions.get(expr.value)
            if function is None:
                self.fail(expr, f"Undefined function {expr.value!r}")
            if len(expr.args) != len(function.params):
                self.fail(expr, f"Function {expr.value!r} expects {len(function.params)} arguments, got {len(expr.args)}")
            for argument, annotation in zip(expr.args, function.param_types):
                actual = self.expr_type(argument)
                if annotation:
                    self.require(actual, annotation, argument)
            return function.return_type or ANY
        if expr.kind == "unary":
            typ = self.expr_type(expr.right)
            self.require(typ, "Bool" if expr.value == "!" else "Int", expr)
            return "Bool" if expr.value == "!" else "Int"
        if expr.kind == "binary":
            left = self.expr_type(expr.left)
            op = expr.value
            if op in {"&&", "||"}:
                self.require(left, "Bool", expr.left)
                right = self.expr_type(expr.right)
                self.require(right, "Bool", expr.right)
                return "Bool"
            right = self.expr_type(expr.right)
            if op in {"==", "!="}:
                return "Bool"
            if op == "+":
                if left == "String" and right == "String":
                    return "String"
                if left == ANY or right == ANY:
                    # A dynamic operand could be an Int or a String.
                    if left not in {ANY, "Int", "String"} or right not in {ANY, "Int", "String"}:
                        self.fail(expr, "'+' requires two integers or two strings")
                    return ANY
            if op in {"+", "-", "*", "/", "<", "<=", ">", ">="}:
                self.require(left, "Int", expr.left)
                self.require(right, "Int", expr.right)
                if op in {"<", "<=", ">", ">="}:
                    return "Bool"
                return "Int"
            self.fail(expr, f"Unsupported operator {op}")
        self.fail(expr, "Unsupported expression")
        raise AssertionError("unreachable")

    def statements(self, statements: tuple[Stmt, ...], *, scoped: bool = False) -> bool:
        if scoped:
            self.scopes.append({})
        try:
            definitely_returns = False
            for stmt in statements:
                if definitely_returns:
                    # Unreachable statements are not analyzed in this first prototype.
                    continue
                if stmt.kind == "declare":
                    current = self.scopes[-1]
                    if stmt.name in current:
                        self.fail(stmt, f"Variable {stmt.name!r} already declared")
                    value_type = self.expr_type(stmt.expr)
                    if stmt.declared_type:
                        self.require(value_type, stmt.declared_type, stmt)
                    current[stmt.name] = Symbol(stmt.declared_type or value_type, stmt.mutable)
                elif stmt.kind == "assign":
                    symbol = self.resolve(stmt.name, stmt)
                    if not symbol.mutable:
                        self.fail(stmt, f"Cannot assign to immutable variable {stmt.name!r}")
                    self.require(self.expr_type(stmt.expr), symbol.type_name, stmt)
                elif stmt.kind == "expr":
                    self.expr_type(stmt.expr)
                elif stmt.kind == "return":
                    value_type = self.expr_type(stmt.expr)
                    annotation = self.current_function.return_type
                    if annotation:
                        self.require(value_type, annotation, stmt)
                    definitely_returns = True
                elif stmt.kind == "if":
                    self.require(self.expr_type(stmt.expr), "Bool", stmt.expr)
                    yes = self.statements(stmt.then_body, scoped=True)
                    no = self.statements(stmt.else_body, scoped=True) if stmt.else_body else False
                    definitely_returns = yes and no
                elif stmt.kind == "while":
                    self.require(self.expr_type(stmt.expr), "Bool", stmt.expr)
                    self.statements(stmt.then_body, scoped=True)
                else:
                    self.fail(stmt, f"Unsupported statement {stmt.kind!r}")
            return definitely_returns
        finally:
            if scoped:
                self.scopes.pop()

    def check(self) -> None:
        for function in self.functions.values():
            self.current_function = function
            self.scopes = [{
                name: Symbol(annotation or ANY, False)
                for name, annotation in zip(function.params, function.param_types)
            }]
            returns = self.statements(function.body)
            if function.return_type not in {None, "Unit", "Any"} and not returns:
                raise SamhusError(
                    f"Function {function.name!r} may exit without returning {function.return_type}",
                    function.token.line, function.token.column,
                )


def check_types(source: str) -> Program:
    """Analyze the source and return its AST if no provable type errors occur."""
    program = parse_program(source)
    TypeChecker(program).check()
    return program
