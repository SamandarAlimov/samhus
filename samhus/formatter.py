"""Deterministic source formatter for the experimental Samhus AST.

Every successful format is designed to be idempotent. Original comments and
some optional parentheses are not preserved; use '--write' only deliberately.
"""
import json

from .parser import Expr, Program, Stmt, Parser
from .values import NULL


def _expr(node: Expr) -> str:
    if node.kind == "literal":
        if type(node.value) is str:
            return json.dumps(node.value, ensure_ascii=False)
        if type(node.value) is bool:
            return "true" if node.value else "false"
        if node.value is NULL:
            return "null"
        return str(node.value)
    if node.kind == "name":
        return node.value
    if node.kind == "call":
        return f"{node.value}({', '.join(_expr(arg) for arg in node.args)})"
    if node.kind == "list":
        return "[" + ", ".join(_expr(item) for item in node.args) + "]"
    if node.kind == "map":
        return "{" + ", ".join(_expr(item.left) + ": " + _expr(item.right) for item in node.args) + "}"
    if node.kind == "index":
        return f"{_expr(node.left)}[{_expr(node.right)}]"
    if node.kind == "unary":
        return f"({node.value}{_expr(node.right)})"
    if node.kind == "binary":
        return f"({_expr(node.left)} {node.value} {_expr(node.right)})"
    raise ValueError(f"Unsupported expression {node.kind!r}")


def _statements(statements: tuple[Stmt, ...], depth: int) -> list[str]:
    indent = "    " * depth
    result: list[str] = []
    for stmt in statements:
        if stmt.kind == "declare":
            prefix = "var" if stmt.mutable else "let"
            annotation = f": {stmt.declared_type}" if stmt.declared_type else ""
            result.append(f"{indent}{prefix} {stmt.name}{annotation} = {_expr(stmt.expr)}")
        elif stmt.kind == "assign":
            result.append(f"{indent}{stmt.name} = {_expr(stmt.expr)}")
        elif stmt.kind == "expr":
            result.append(f"{indent}{_expr(stmt.expr)}")
        elif stmt.kind == "return":
            result.append(f"{indent}return {_expr(stmt.expr)}")
        elif stmt.kind in {"if", "while"}:
            result.append(f"{indent}{stmt.kind} {_expr(stmt.expr)} {{")
            result.extend(_statements(stmt.then_body, depth + 1))
            result.append(f"{indent}}}")
            if stmt.kind == "if" and stmt.else_body:
                result[-1] += " else {"
                result.extend(_statements(stmt.else_body, depth + 1))
                result.append(f"{indent}}}")
        else:
            raise ValueError(f"Unsupported statement {stmt.kind!r}")
    return result


def format_ast(program: Program) -> str:
    lines: list[str] = []
    for imported in program.imports:
        lines.append("import " + json.dumps(imported.path, ensure_ascii=False))
    if lines and program.functions:
        lines.append("")
    for fn in program.functions:
        params = ", ".join(
            f"{name}: {annotation}" if annotation else name
            for name, annotation in zip(fn.params, fn.param_types)
        )
        result = f"fn {fn.name}({params})"
        if fn.return_type:
            result += f" -> {fn.return_type}"
        lines.append(result + " {")
        lines.extend(_statements(fn.body, 1))
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_program(source: str) -> str:
    return format_ast(Parser(source).parse_program(allow_imports=True, require_main=False))


def contains_comments(source: str) -> bool:
    """Recognize // comments while ignoring // inside quoted string literals."""
    inside_string = False
    escaped = False
    index = 0
    while index < len(source):
        ch = source[index]
        if inside_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                inside_string = False
        elif ch == '"':
            inside_string = True
        elif source.startswith("//", index):
            return True
        index += 1
    return False
