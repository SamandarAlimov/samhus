"""Experimental static value hints for verified CFG IR, not typed SSA.

Uses the source checker and propagates conservative stack types over reachable
bytecode. At joins, conflicting types become Any. No runtime behavior changes.
"""
from collections import deque
from dataclasses import dataclass

from .ir import ProgramIR, compile_ir, lower_ir
from .parser import Program
from .stdlib import BUILTIN_SIGNATURES
from .typecheck import TypeChecker
from .values import element_type, map_value_type, result_type, type_name
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class TypeState:
    stack: tuple[str, ...]
    scopes: tuple[tuple[tuple[str, str], ...], ...]


@dataclass(frozen=True)
class TypedIR:
    cfg: ProgramIR
    # One tuple per function: (instruction offset, stack types, locals)
    states: tuple[tuple[tuple[int, TypeState], ...], ...]

    def disassemble(self) -> str:
        lines = []
        for fn, states in zip(self.cfg.functions, self.states):
            entries = dict(states)
            lines.append(f"fn {fn.name}:")
            offset = 0
            for block in fn.blocks:
                state = entries[offset]
                variables = ", ".join(k + ":" + v for scope in state.scopes for k, v in scope)
                lines.append(f"  {block.label}: stack={state.stack!r} locals={variables or '(none)'}")
                for instr in block.instructions:
                    state = entries[offset]
                    argument = "" if instr.arg is None else " " + repr(instr.arg)
                    current = ", ".join(
                        name + ":" + kind
                        for scope in state.scopes for name, kind in scope
                    ) or "(none)"
                    lines.append(
                        f"    {offset:04} {instr.op}{argument} "
                        f"; stack={state.stack!r} locals={current}"
                    )
                    offset += 1
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def _join(a: TypeState, b: TypeState, fn: str, pc: int) -> TypeState:
    if len(a.stack) != len(b.stack) or len(a.scopes) != len(b.scopes):
        raise BytecodeValidationError(f"{fn}: type-state shape mismatch at {pc}")
    def merge(x, y):
        return x if x == y else "Any"
    scopes = []
    for left, right in zip(a.scopes, b.scopes):
        if tuple(k for k, _ in left) != tuple(k for k, _ in right):
            raise BytecodeValidationError(f"{fn}: symbol-state mismatch at {pc}")
        scopes.append(tuple((k, merge(v, w)) for (k,v),(_,w) in zip(left,right)))
    return TypeState(tuple(merge(x,y) for x,y in zip(a.stack,b.stack)), tuple(scopes))


def _infer_call(name: str, args: tuple[str,...], functions) -> str:
    if name == "result_ok" and len(args) == 1:
        return "Result[" + args[0] + "]"
    if name in {"append", "map_set"} and args:
        return args[0]
    if name in {"result_value", "result_or"} and args:
        return result_type(args[0]) or "Any"
    if name in BUILTIN_SIGNATURES:
        return BUILTIN_SIGNATURES[name][1]
    fn = functions.get(name)
    return fn.return_type or "Any" if fn else "Any"


def _operation(op, a, b):
    if op in {"==","!=","<","<=",">",">="}:
        return "Bool"
    if "Any" in (a,b):
        return "Any"
    if op == "+" and a == b == "String":
        return "String"
    if "Decimal" in (a,b):
        return "Any" if "Float" in (a,b) else "Decimal"
    if "Float" in (a,b):
        return "Float"
    return "Int" if a == b == "Int" else "Any"


def _step(state, ins, functions):
    stack = list(state.stack)
    scopes = [dict(scope) for scope in state.scopes]
    op, arg = ins.op, ins.arg
    if op == "PUSH":
        stack.append(type_name(arg))
    elif op == "LOAD":
        value = next((scope[arg] for scope in reversed(scopes) if arg in scope), "Any")
        stack.append(value)
    elif op == "SCOPE_IN":
        scopes.append({})
    elif op == "SCOPE_OUT":
        scopes.pop()
    elif op == "DECLARE":
        name, mutable, annotation = arg
        actual = stack.pop()
        scopes[-1][name] = annotation or actual
    elif op == "ASSIGN":
        actual = stack.pop()
        for scope in reversed(scopes):
            if arg in scope:
                scope[arg] = scope[arg] if scope[arg] == actual else "Any"
                break
    elif op == "CALL":
        name, count = arg
        args = tuple(stack[-count:]) if count else ()
        if count:
            del stack[-count:]
        stack.append(_infer_call(name, args, functions))
    elif op == "UNARY":
        kind = stack.pop()
        stack.append("Bool" if arg == "!" else kind)
    elif op == "BINARY":
        right, left = stack.pop(), stack.pop()
        stack.append(_operation(arg,left,right))
    elif op == "INDEX":
        index, collection = stack.pop(), stack.pop()
        stack.append("String" if collection == "String" else
                     (element_type(collection) or map_value_type(collection) or "Any"))
    elif op in {"BUILD_LIST","BUILD_MAP"}:
        n = arg if op == "BUILD_LIST" else 2 * arg
        members = tuple(stack[-n:]) if n else ()
        if n:
            del stack[-n:]
        value_types = members if op == "BUILD_LIST" else members[1::2]
        first = value_types[0] if value_types else "Any"
        inner = first if all(item == first for item in value_types) else "Any"
        stack.append("List[" + inner + "]" if op == "BUILD_LIST"
                     else "Map[String," + inner + "]")
    elif op in {"POP","BRANCH_FALSE","RETURN"}:
        stack.pop()
    elif op in {"KEEP_TRUE","KEEP_FALSE","EXPECT_BOOL","ASSERT_FRESH",
                "ASSERT_MUTABLE","JUMP","TICK","RETURN_VOID"}:
        pass
    else:
        raise BytecodeValidationError(f"Unknown type-analysis opcode {op}")
    return TypeState(tuple(stack), tuple(tuple(sorted(x.items())) for x in scopes))


def _successors(code, pc):
    ins = code[pc]
    if ins.op in {"RETURN", "RETURN_VOID"}:
        return ()
    if ins.op == "JUMP":
        return (ins.arg,)
    if ins.op in {"KEEP_TRUE","KEEP_FALSE"}:
        return (pc+1,ins.arg)
    if ins.op == "BRANCH_FALSE":
        return (pc+1,ins.arg[1])
    return (pc+1,)


def analyze_ir(cfg: ProgramIR) -> TypedIR:
    """Annotate IR without claiming complete static typing or memory safety."""
    functions = {fn.name: fn for fn in cfg.functions}
    code = lower_ir(cfg)
    analyses = []
    for fn, compiled in zip(cfg.functions, code.functions):
        instructions = compiled.instructions
        initial = TypeState((), (tuple(sorted(zip(
            fn.params, (param or "Any" for param in fn.param_types)
        ))),))
        states = {0: initial}
        queue = deque([0])
        changes = 0
        while queue:
            changes += 1
            if changes > len(instructions) * 40 + 100:
                raise BytecodeValidationError(f"{fn.name}: type analysis did not converge")
            pc = queue.popleft()
            out = _step(states[pc], instructions[pc], functions)
            for dest in _successors(instructions, pc):
                if not 0 <= dest < len(instructions):
                    raise BytecodeValidationError(f"{fn.name}: invalid successor {dest}")
                old = states.get(dest)
                new = out if old is None else _join(old, out, fn.name, dest)
                if old != new:
                    states[dest] = new
                    queue.append(dest)
        analyses.append(tuple(sorted(states.items())))
    return TypedIR(cfg, tuple(analyses))


def compile_typed_ir(program: Program) -> TypedIR:
    TypeChecker(program).check()
    return analyze_ir(compile_ir(program))
