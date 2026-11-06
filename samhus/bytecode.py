"""Prototype stack-bytecode compiler for Samhus.

This is a second, independent *execution path* through the language AST.
It does not generate native code or a portable bytecode file format.
None of the opcode names or semantics constitute a stable language ABI.
"""
from dataclasses import dataclass
from typing import Any

from .lexer import Token
from .parser import Expr, Function, Program, Stmt, parse_program


@dataclass(frozen=True)
class Instruction:
    op: str
    arg: Any
    token: Token


@dataclass(frozen=True)
class Code:
    name: str
    params: tuple[str, ...]
    param_types: tuple[str | None, ...]
    return_type: str | None
    token: Token
    instructions: tuple[Instruction, ...]


@dataclass(frozen=True)
class Bytecode:
    functions: tuple[Code, ...]

    def disassemble(self) -> str:
        result = []
        for function in self.functions:
            result.append(f"fn {function.name}({', '.join(function.params)}) -> {function.return_type or 'Any'}:")
            for offset, inst in enumerate(function.instructions):
                argument = "" if inst.arg is None else f" {inst.arg!r}"
                result.append(f"  {offset:04} {inst.op}{argument}  ; {inst.token.line}:{inst.token.column}")
            result.append("")
        return "\n".join(result).rstrip() + "\n"


class _Emitter:
    def __init__(self):
        self.code: list[Instruction] = []

    def emit(self, op: str, arg: Any, token: Token) -> int:
        index = len(self.code)
        self.code.append(Instruction(op, arg, token))
        return index

    def patch(self, index: int, target: int) -> None:
        old = self.code[index]
        self.code[index] = Instruction(old.op, target, old.token)

    def expression(self, expr: Expr) -> None:
        kind = expr.kind
        if kind == "literal":
            self.emit("PUSH", expr.value, expr.token)
        elif kind == "name":
            self.emit("LOAD", expr.value, expr.token)
        elif kind == "unary":
            self.expression(expr.right)
            self.emit("UNARY", expr.value, expr.token)
        elif kind == "binary":
            if expr.value in {"&&", "||"}:
                self.expression(expr.left)
                jump = self.emit("KEEP_FALSE" if expr.value == "&&" else "KEEP_TRUE", None, expr.token)
                self.emit("POP", None, expr.token)
                self.expression(expr.right)
                self.emit("EXPECT_BOOL", expr.value, expr.token)
                self.patch(jump, len(self.code))
            else:
                self.expression(expr.left)
                self.expression(expr.right)
                self.emit("BINARY", expr.value, expr.token)
        elif kind == "list":
            for argument in expr.args:
                self.expression(argument)
            self.emit("BUILD_LIST", len(expr.args), expr.token)
        elif kind == "index":
            self.expression(expr.left)
            self.expression(expr.right)
            self.emit("INDEX", None, expr.token)
        elif kind == "call":
            for argument in expr.args:
                self.expression(argument)
            self.emit("CALL", (expr.value, len(expr.args)), expr.token)
        else:
            raise AssertionError(f"Unexpected AST expression {kind!r}")

    def block(self, body: tuple[Stmt, ...], scoped: bool) -> None:
        if scoped:
            self.emit("SCOPE_IN", None, body[0].token if body else self._fallback())
        for stmt in body:
            self.statement(stmt)
        if scoped:
            self.emit("SCOPE_OUT", None, body[-1].token if body else self._fallback())

    def _fallback(self) -> Token:
        # Scope markers have no user-visible errors in valid compiler output.
        return Token("SCOPE", "", 1, 1)

    def statement(self, stmt: Stmt) -> None:
        self.emit("TICK", None, stmt.token)
        if stmt.kind == "declare":
            self.emit("ASSERT_FRESH", stmt.name, stmt.token)
            self.expression(stmt.expr)
            self.emit("DECLARE", (stmt.name, stmt.mutable, stmt.declared_type), stmt.token)
        elif stmt.kind == "assign":
            # Tree walker checks immutability/undefined name *before* RHS eval.
            self.emit("ASSERT_MUTABLE", stmt.name, stmt.token)
            self.expression(stmt.expr)
            self.emit("ASSIGN", stmt.name, stmt.token)
        elif stmt.kind == "expr":
            self.expression(stmt.expr)
            self.emit("POP", None, stmt.token)
        elif stmt.kind == "return":
            self.expression(stmt.expr)
            self.emit("RETURN", None, stmt.token)
        elif stmt.kind == "if":
            self.expression(stmt.expr)
            no_branch = self.emit("BRANCH_FALSE", ("if", -1), stmt.token)
            self.block(stmt.then_body, scoped=True)
            end_jump = self.emit("JUMP", -1, stmt.token)
            self.patch(no_branch, ("if", len(self.code)))
            if stmt.else_body:
                self.block(stmt.else_body, scoped=True)
            self.patch(end_jump, len(self.code))
        elif stmt.kind == "while":
            start = len(self.code)
            self.emit("TICK", None, stmt.token)  # Per-loop iteration, even empty body.
            self.expression(stmt.expr)
            end_jump = self.emit("BRANCH_FALSE", ("while", -1), stmt.token)
            self.block(stmt.then_body, scoped=True)
            self.emit("JUMP", start, stmt.token)
            self.patch(end_jump, ("while", len(self.code)))
        else:
            raise AssertionError(f"Unexpected AST statement {stmt.kind!r}")


def compile_ast(program: Program) -> Bytecode:
    functions: list[Code] = []
    for function in program.functions:
        emit = _Emitter()
        emit.block(function.body, scoped=False)
        emit.emit("RETURN_VOID", None, function.token)
        functions.append(Code(
            function.name, function.params, function.param_types,
            function.return_type, function.token, tuple(emit.code)
        ))
    program_code = Bytecode(tuple(functions))
    # Validate internal control-flow invariants before the VM may execute it.
    from .verify import verify_bytecode
    verify_bytecode(program_code)
    return program_code


def compile_source(source: str) -> Bytecode:
    """Compile parsed Samhus source to an in-memory stack bytecode program."""
    return compile_ast(parse_program(source))
