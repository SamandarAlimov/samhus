"""Opt-in, conservative prototype static type checker for Samhus.

Unannotated parameters and function returns are Any. Typed declarations and
known literal expressions are checked; Any permits dynamic checks at runtime.
This is an experimental analyzer, not a soundness proof.
"""
from dataclasses import dataclass

from .errors import SamhusError
from .parser import Expr, Function, Program, Stmt, parse_program
from .stdlib import BUILTIN_SIGNATURES
from .values import element_type, map_value_type, NULL

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
        if ANY in {actual, expected} or actual == expected:
            return True
        a, e = element_type(actual), element_type(expected)
        if a is not None and e is not None:
            return TypeChecker.compatible(a, e)
        a, e = map_value_type(actual), map_value_type(expected)
        return a is not None and e is not None and TypeChecker.compatible(a, e)

    def require(self, actual: Type, expected: Type, node: Expr | Stmt) -> None:
        if not self.compatible(actual, expected):
            self.fail(node, f"Type mismatch: expected {expected}, got {actual}")

    def require_expr(self, expr: Expr, expected: Type) -> Type:
        # Inspect literals recursively before checking the aggregate:
        # the diagnostic now points to the mismatched item, not its container.
        inner = element_type(expected)
        if inner is not None and expr.kind == "list":
            for item in expr.args:
                self.require_expr(item, inner)
        inner = map_value_type(expected)
        if inner is not None and expr.kind == "map":
            for entry in expr.args:
                self.require_expr(entry.left, "String")
                self.require_expr(entry.right, inner)
        actual = self.expr_type(expr)
        self.require(actual, expected, expr)
        return actual

    def expr_type(self, expr: Expr) -> Type:
        if expr.kind == "literal":
            if type(expr.value) is bool:
                return "Bool"
            if type(expr.value) is int:
                return "Int"
            if type(expr.value) is float:
                return "Float"
            if expr.value is NULL:
                return "Null"
            if type(expr.value) is str:
                return "String"
            self.fail(expr, "Unsupported literal type")
        if expr.kind == "name":
            return self.resolve(expr.value, expr).type_name
        if expr.kind == "map":
            value_types = []
            for entry in expr.args:
                self.require_expr(entry.left, "String")
                value_types.append(self.expr_type(entry.right))
            if not value_types:
                return "Map[String,Any]"
            first = value_types[0]
            return "Map[String," + (first if all(item == first for item in value_types) else "Any") + "]"
        if expr.kind == "list":
            types = [self.expr_type(item) for item in expr.args]
            if not types:
                return "List[Any]"
            first = types[0]
            return "List[" + (first if all(item == first for item in types) else "Any") + "]"
        if expr.kind == "index":
            target = self.expr_type(expr.left)
            if target == ANY:
                # Dynamic JSON values may be Maps (String key) or Lists (Int
                # index). Validate expression itself; runtime checks the key.
                self.expr_type(expr.right)
                return ANY
            key_type = "String" if map_value_type(target) is not None else "Int"
            self.require_expr(expr.right, key_type)
            mapped = map_value_type(target)
            if mapped is not None:
                return mapped
            if target == "String":
                return "String"
            inner = element_type(target)
            if inner is None:
                self.fail(expr, f"Indexing requires List or String, got {target}")
            return inner
        if expr.kind == "call":
            if expr.value in {"map_set", "map_has", "map_keys"}:
                count = {"map_set": 3, "map_has": 2, "map_keys": 1}[expr.value]
                if len(expr.args) != count:
                    self.fail(expr, f"{expr.value} expects {count} arguments, got {len(expr.args)}")
                target = self.expr_type(expr.args[0])
                val = map_value_type(target)
                if target != ANY and val is None:
                    self.fail(expr, f"{expr.value} expects Map, got {target}")
                if len(expr.args) >= 2:
                    self.require_expr(expr.args[1], "String")
                if expr.value == "map_set":
                    self.require_expr(expr.args[2], val or ANY)
                    return target
                return "Bool" if expr.value == "map_has" else "List[String]"
            if expr.value == "append":
                if len(expr.args) != 2:
                    self.fail(expr, f"append expects 2 arguments, got {len(expr.args)}")
                target_type = self.expr_type(expr.args[0])
                inner_type = element_type(target_type)
                if target_type == ANY:
                    self.expr_type(expr.args[1])
                    return ANY
                if inner_type is None:
                    self.fail(expr, f"append expects List, got {target_type}")
                self.require_expr(expr.args[1], inner_type)
                return target_type
            if expr.value == "len":
                if len(expr.args) != 1:
                    self.fail(expr, f"len expects 1 argument, got {len(expr.args)}")
                candidate = self.expr_type(expr.args[0])
                if candidate not in (ANY, "String") and element_type(candidate) is None and map_value_type(candidate) is None:
                    self.fail(expr, f"Type mismatch: expected String, got {candidate} (or List)")
                return "Int"
            signature = BUILTIN_SIGNATURES.get(expr.value)
            if signature is not None:
                params, return_type = signature
                if len(expr.args) != len(params):
                    self.fail(expr, f"{expr.value} expects {len(params)} argument, got {len(expr.args)}")
                for argument, expected in zip(expr.args, params):
                    if expected != ANY:
                        self.require_expr(argument, expected)
                    else:
                        self.expr_type(argument)
                return return_type
            function = self.functions.get(expr.value)
            if function is None:
                self.fail(expr, f"Undefined function {expr.value!r}")
            if len(expr.args) != len(function.params):
                self.fail(expr, f"Function {expr.value!r} expects {len(function.params)} arguments, got {len(expr.args)}")
            for argument, annotation in zip(expr.args, function.param_types):
                if annotation:
                    self.require_expr(argument, annotation)
                else:
                    self.expr_type(argument)
            return function.return_type or ANY
        if expr.kind == "unary":
            typ = self.expr_type(expr.right)
            if expr.value == "!":
                self.require(typ, "Bool", expr)
                return "Bool"
            if typ not in {"Int", "Float", ANY}:
                self.require(typ, "Int", expr)
            return typ
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
            if op in {"+", "-", "*", "/", "<", "<=", ">", ">="}:
                ordering = op in {"<", "<=", ">", ">="}
                if op == "+" and left == "String" and right == "String":
                    return "String"
                allowed = {"Int", "Float", ANY}
                if op == "+":
                    allowed.add("String")
                if left not in allowed:
                    self.require(left, "Int", expr.left)
                if right not in allowed:
                    self.require(right, "Int", expr.right)
                if op == "+" and (left == "String" or right == "String"):
                    if left == ANY or right == ANY:
                        return ANY
                    # The other known type is numeric, not String.
                    self.require(left if left != "String" else right, "String", expr)
                if ordering:
                    return "Bool"
                if left == ANY or right == ANY:
                    return ANY
                if "Float" in (left, right):
                    return "Float"
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
                        self.require_expr(stmt.expr, stmt.declared_type)
                    current[stmt.name] = Symbol(stmt.declared_type or value_type, stmt.mutable)
                elif stmt.kind == "assign":
                    symbol = self.resolve(stmt.name, stmt)
                    if not symbol.mutable:
                        self.fail(stmt, f"Cannot assign to immutable variable {stmt.name!r}")
                    self.require_expr(stmt.expr, symbol.type_name)
                elif stmt.kind == "expr":
                    self.expr_type(stmt.expr)
                elif stmt.kind == "return":
                    annotation = self.current_function.return_type
                    if annotation:
                        self.require_expr(stmt.expr, annotation)
                    else:
                        self.expr_type(stmt.expr)
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
