"""Experimental stack virtual machine for compiled Samhus programs.

Bytecode is produced internally by samhus.bytecode; arbitrary/untrusted
instruction streams are unsupported and this VM is NOT a security sandbox.
"""
from dataclasses import dataclass
from io import StringIO
import sys
from typing import TextIO

from .bytecode import Bytecode, Code, Instruction, compile_source
from .errors import SamhusError
from .lexer import Token
from .runtime import Binding, Value, value_type
from .stdlib import BUILTIN_SIGNATURES, call_builtin


@dataclass
class _Frame:
    scopes: list[dict[str, Binding]]
    stack: list[Value]
    ip: int = 0


class VirtualMachine:
    def __init__(self, output: TextIO, *, max_steps: int = 100_000, max_calls: int = 128):
        if max_steps < 1 or max_calls < 1:
            raise ValueError("Execution limits must be positive")
        self.output = output
        self.functions: dict[str, Code] = {}
        self.max_steps = max_steps
        self.max_calls = max_calls
        self.steps = 0
        self.call_depth = 0

    def error(self, token: Token, message: str) -> None:
        raise SamhusError(message, token.line, token.column)

    def tick(self, token: Token) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            self.error(token, f"Execution step limit exceeded ({self.max_steps})")

    def enforce(self, expected: str | None, value: Value, token: Token) -> None:
        if expected is not None and expected != "Any" and expected != value_type(value):
            self.error(token, f"Type mismatch: expected {expected}, got {value_type(value)}")

    def binding(self, frame: _Frame, name: str, token: Token) -> Binding:
        for scope in reversed(frame.scopes):
            if name in scope:
                return scope[name]
        self.error(token, f"Undefined variable {name!r}")
        raise AssertionError("unreachable")

    def unary(self, op: str, right: Value, token: Token) -> Value:
        if op == "!":
            if type(right) is not bool:
                self.error(token, "'!' requires a boolean")
            return not right
        if type(right) is not int:
            self.error(token, "Unary '-' requires an integer")
        return -right

    def binary(self, op: str, left: Value, right: Value, token: Token) -> Value:
        if op in {"==", "!="}:
            eq = type(left) is type(right) and left == right
            return eq if op == "==" else not eq
        if op == "+" and type(left) is str and type(right) is str:
            return left + right
        if type(left) is not int or type(right) is not int:
            self.error(token, f"'{op}' requires integers (or two strings for '+')")
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                self.error(token, "Division by zero")
            quotient = abs(left) // abs(right)
            return -quotient if (left < 0) != (right < 0) else quotient
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        raise AssertionError(f"Unsupported compiled operator: {op}")

    def invoke(self, name: str, args: tuple[Value, ...], token: Token) -> Value:
        self.tick(token)
        if name in BUILTIN_SIGNATURES:
            return call_builtin(name, args, token, self.output)
        function = self.functions.get(name)
        if function is None:
            self.error(token, f"Undefined function {name!r}")
        if len(args) != len(function.params):
            self.error(token, f"Function {name!r} expects {len(function.params)} arguments, got {len(args)}")
        if self.call_depth >= self.max_calls:
            self.error(token, f"Function call depth limit exceeded ({self.max_calls})")
        for argument, expected in zip(args, function.param_types):
            self.enforce(expected, argument, token)
        frame = _Frame([{
            key: Binding(value, False, declared)
            for key, value, declared in zip(function.params, args, function.param_types)
        }], [])
        self.call_depth += 1
        try:
            result = self._execute(frame, function)
            self.enforce(function.return_type, result, token)
            return result
        finally:
            self.call_depth -= 1

    def _execute(self, frame: _Frame, function: Code) -> Value:
        instructions = function.instructions
        stack = frame.stack
        while frame.ip < len(instructions):
            ins = instructions[frame.ip]
            frame.ip += 1
            op, arg, token = ins.op, ins.arg, ins.token
            if op == "TICK":
                self.tick(token)
            elif op == "PUSH":
                stack.append(arg)
            elif op == "POP":
                stack.pop()
            elif op == "LOAD":
                stack.append(self.binding(frame, arg, token).value)
            elif op == "ASSERT_MUTABLE":
                if not self.binding(frame, arg, token).mutable:
                    self.error(token, f"Cannot assign to immutable variable {arg!r}")
            elif op == "ASSERT_FRESH":
                if arg in frame.scopes[-1]:
                    self.error(token, f"Variable {arg!r} already declared")
            elif op == "DECLARE":
                name, mutable, type_name = arg
                scope = frame.scopes[-1]
                if name in scope:
                    self.error(token, f"Variable {name!r} already declared")
                value = stack.pop()
                self.enforce(type_name, value, token)
                scope[name] = Binding(value, mutable, type_name)
            elif op == "ASSIGN":
                binding = self.binding(frame, arg, token)
                value = stack.pop()
                self.enforce(binding.declared_type, value, token)
                binding.value = value
            elif op == "SCOPE_IN":
                frame.scopes.append({})
            elif op == "SCOPE_OUT":
                frame.scopes.pop()
            elif op == "UNARY":
                stack.append(self.unary(arg, stack.pop(), token))
            elif op == "BINARY":
                right, left = stack.pop(), stack.pop()
                stack.append(self.binary(arg, left, right, token))
            elif op == "CALL":
                name, count = arg
                arguments = tuple(stack[-count:]) if count else ()
                if count:
                    del stack[-count:]
                stack.append(self.invoke(name, arguments, token))
            elif op == "BRANCH_FALSE":
                kind, target = arg
                condition = stack.pop()
                if type(condition) is not bool:
                    self.error(token, f"{'If' if kind == 'if' else 'While'} condition must be a boolean")
                if not condition:
                    frame.ip = target
            elif op in {"KEEP_FALSE", "KEEP_TRUE"}:
                left = stack[-1]
                if type(left) is not bool:
                    self.error(token, f"'{'&&' if op == 'KEEP_FALSE' else '||'}' requires booleans")
                if (not left if op == "KEEP_FALSE" else left):
                    frame.ip = arg
            elif op == "EXPECT_BOOL":
                right = stack[-1]
                if type(right) is not bool:
                    self.error(token, f"'{arg}' requires booleans")
            elif op == "JUMP":
                frame.ip = arg
            elif op == "RETURN":
                return stack.pop()
            elif op == "RETURN_VOID":
                return None
            else:
                raise AssertionError(f"Invalid internal bytecode opcode {op!r}")
        raise AssertionError("Compiled function missing return instruction")

    def run(self, program: Bytecode) -> None:
        self.functions = {fn.name: fn for fn in program.functions}
        function = self.functions["main"]
        self.invoke("main", (), function.token)


def run_vm(source: str, output: TextIO | None = None, *, max_steps: int = 100_000) -> None:
    """Compile and run trusted source through the independent VM path."""
    VirtualMachine(output if output is not None else sys.stdout, max_steps=max_steps).run(compile_source(source))


def run_vm_to_string(source: str, *, max_steps: int = 100_000) -> str:
    output = StringIO()
    run_vm(source, output=output, max_steps=max_steps)
    return output.getvalue()
