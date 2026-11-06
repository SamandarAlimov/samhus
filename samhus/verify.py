"""Conservative control-flow verifier for compiler-produced Samhus bytecode.

Checks reachable instruction targets, stack heights, scope nesting and
consistent control-flow merges. This is not a proof of memory safety and is
not intended to validate hostile/untrusted serialized bytecode.
"""
from collections import deque
from .bytecode import Bytecode, Code, Instruction


class BytecodeValidationError(ValueError):
    pass


def verify_function(function: Code) -> None:
    code = function.instructions
    if not code:
        raise BytecodeValidationError(f"{function.name}: empty function body")
    states: dict[int, tuple[int, int]] = {0: (0, 0)}
    pending = deque([0])
    while pending:
        ip = pending.popleft()
        stack, scopes = states[ip]
        if not 0 <= ip < len(code):
            raise BytecodeValidationError(f"{function.name}: invalid instruction index {ip}")
        inst = code[ip]
        op, arg = inst.op, inst.arg
        popped = 0
        pushed = 0
        scope_change = 0
        terminal = False
        if op in {"TICK", "ASSERT_FRESH", "ASSERT_MUTABLE", "JUMP"}:
            pass
        elif op in {"PUSH", "LOAD"}:
            pushed = 1
        elif op in {"POP", "DECLARE", "ASSIGN", "BRANCH_FALSE"}:
            popped = 1
        elif op == "UNARY":
            popped, pushed = 1, 1
        elif op == "BINARY":
            popped, pushed = 2, 1
        elif op == "CALL":
            if not isinstance(arg, tuple) or len(arg) != 2 or type(arg[1]) is not int or arg[1] < 0:
                raise BytecodeValidationError(f"{function.name}: malformed CALL at {ip}")
            popped, pushed = arg[1], 1
        elif op in {"KEEP_FALSE", "KEEP_TRUE", "EXPECT_BOOL"}:
            popped, pushed = 1, 1
        elif op == "SCOPE_IN":
            scope_change = 1
        elif op == "SCOPE_OUT":
            scope_change = -1
        elif op == "RETURN":
            popped, terminal = 1, True
        elif op == "RETURN_VOID":
            terminal = True
        else:
            raise BytecodeValidationError(f"{function.name}: unknown opcode {op!r} at {ip}")
        if stack < popped:
            raise BytecodeValidationError(f"{function.name}: stack underflow at instruction {ip}: {op}")
        after_stack = stack - popped + pushed
        after_scope = scopes + scope_change
        if after_scope < 0:
            raise BytecodeValidationError(f"{function.name}: scope underflow at instruction {ip}")
        if terminal:
            if after_stack:
                raise BytecodeValidationError(f"{function.name}: nonempty stack at return instruction {ip}")
            continue
        if op == "JUMP":
            destinations = [arg]
        elif op in {"KEEP_FALSE", "KEEP_TRUE"}:
            destinations = [ip + 1, arg]
        elif op == "BRANCH_FALSE":
            if not isinstance(arg, tuple) or len(arg) != 2:
                raise BytecodeValidationError(f"{function.name}: malformed branch at {ip}")
            destinations = [ip + 1, arg[1]]
        else:
            destinations = [ip + 1]
        for destination in destinations:
            if type(destination) is not int or not 0 <= destination < len(code):
                raise BytecodeValidationError(f"{function.name}: invalid branch target {destination!r}")
            new_state = (after_stack, after_scope)
            previous = states.get(destination)
            if previous is None:
                states[destination] = new_state
                pending.append(destination)
            elif previous != new_state:
                raise BytecodeValidationError(
                    f"{function.name}: conflicting stack/scope states at {destination}: {previous} vs {new_state}"
                )


def verify_bytecode(program: Bytecode) -> None:
    for function in program.functions:
        verify_function(function)
