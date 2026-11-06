"""Experimental control-flow IR for Samhus's Python-hosted compiler.

Stack-based, explicit basic blocks, predecessor/successor edges and verified
entry stack/scope states. This is NOT typed SSA, a stable bytecode ABI or
the production native compiler IR. The native C11 experiment still uses AST.
"""
from dataclasses import dataclass, replace

from .bytecode import Bytecode, Code, Instruction, compile_ast
from .parser import Program
from .verify import BytecodeValidationError, verify_function


_TERMINATORS = frozenset({"JUMP", "BRANCH_FALSE", "KEEP_FALSE", "KEEP_TRUE",
                          "RETURN", "RETURN_VOID"})
_JUMPS = frozenset({"JUMP", "BRANCH_FALSE", "KEEP_FALSE", "KEEP_TRUE"})


@dataclass(frozen=True)
class BasicBlock:
    label: str
    original_offset: int
    entry_stack: int
    entry_scopes: int
    instructions: tuple[Instruction, ...]
    successors: tuple[str, ...]


@dataclass(frozen=True)
class FunctionIR:
    name: str
    params: tuple[str, ...]
    param_types: tuple[str | None, ...]
    return_type: str | None
    token: object
    blocks: tuple[BasicBlock, ...]


@dataclass(frozen=True)
class ProgramIR:
    functions: tuple[FunctionIR, ...]

    def disassemble(self) -> str:
        lines = []
        for function in self.functions:
            signature = ", ".join(
                name if kind is None else f"{name}: {kind}"
                for name, kind in zip(function.params, function.param_types)
            )
            lines.append(f"fn {function.name}({signature}) -> {function.return_type or 'Any'}:")
            for block in function.blocks:
                outgoing = ", ".join(block.successors) if block.successors else "(return)"
                lines.append(
                    f"  {block.label}: stack={block.entry_stack} scopes={block.entry_scopes}"
                    f" -> {outgoing}"
                )
                for inst in block.instructions:
                    arg = "" if inst.arg is None else " " + repr(inst.arg)
                    lines.append(f"    {inst.op}{arg}  ; {inst.token.line}:{inst.token.column}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def _target(instruction: Instruction) -> int:
    if instruction.op == "JUMP" or instruction.op in {"KEEP_TRUE", "KEEP_FALSE"}:
        return instruction.arg
    if instruction.op == "BRANCH_FALSE":
        return instruction.arg[1]
    raise ValueError(f"No branch target for {instruction.op}")


def _branch_labels(inst: Instruction, label_by_offset: dict[int, str]) -> Instruction:
    if inst.op not in _JUMPS:
        return inst
    label = label_by_offset[_target(inst)]
    if inst.op == "BRANCH_FALSE":
        return replace(inst, arg=(inst.arg[0], label))
    return replace(inst, arg=label)


def _unique(labels: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(labels))


def from_bytecode(bytecode: Bytecode) -> ProgramIR:
    functions = []
    for function in bytecode.functions:
        states = verify_function(function)
        code = function.instructions
        leaders = {0}
        for i, instruction in enumerate(code):
            if instruction.op in _JUMPS:
                leaders.add(_target(instruction))
            if instruction.op in _TERMINATORS and i + 1 < len(code):
                leaders.add(i + 1)
        starts = sorted(leaders)
        label_by_offset = {start: f"b{start:04}" for start in starts}
        blocks = []
        for i, start in enumerate(starts):
            # Ignore unreachable instructions/blocks but do not change the
            # execution order within each reachable basic block.
            if start not in states:
                continue
            stop = starts[i + 1] if i + 1 < len(starts) else len(code)
            segment = code[start:stop]
            if not segment:
                continue
            final = segment[-1]
            successors = []
            if final.op in {"JUMP", "KEEP_FALSE", "KEEP_TRUE", "BRANCH_FALSE"}:
                if final.op != "JUMP":
                    if stop < len(code):
                        successors.append(label_by_offset[stop])
                successors.append(label_by_offset[_target(final)])
            elif final.op not in {"RETURN", "RETURN_VOID"} and stop < len(code):
                successors.append(label_by_offset[stop])
            stack, scopes = states[start]
            blocks.append(BasicBlock(
                label_by_offset[start], start, stack, scopes,
                tuple(_branch_labels(inst, label_by_offset) for inst in segment),
                _unique(successors),
            ))
        functions.append(FunctionIR(
            function.name, function.params, function.param_types,
            function.return_type, function.token, tuple(blocks),
        ))
    result = ProgramIR(tuple(functions))
    verify_ir(result)
    return result


def compile_ir(program: Program) -> ProgramIR:
    """Lower a parsed/link-resolved Program AST to validated basic blocks."""
    return from_bytecode(compile_ast(program))


def _remap(inst: Instruction, offsets: dict[str, int]) -> Instruction:
    if inst.op not in _JUMPS:
        return inst
    target = inst.arg[1] if inst.op == "BRANCH_FALSE" else inst.arg
    if not isinstance(target, str) or target not in offsets:
        raise BytecodeValidationError(f"IR has unknown target label {target!r}")
    if inst.op == "BRANCH_FALSE":
        if (not isinstance(inst.arg, tuple) or len(inst.arg) != 2 or
                inst.arg[0] not in {"if", "while"}):
            raise BytecodeValidationError("IR has malformed conditional jump")
        return replace(inst, arg=(inst.arg[0], offsets[target]))
    return replace(inst, arg=offsets[target])


def _lower_function(function: FunctionIR) -> Code:
    offsets = {}
    current = 0
    for block in function.blocks:
        if block.label in offsets:
            raise BytecodeValidationError(f"{function.name}: duplicate block {block.label}")
        offsets[block.label] = current
        current += len(block.instructions)
    lowered = tuple(
        _remap(inst, offsets)
        for block in function.blocks for inst in block.instructions
    )
    return Code(function.name, function.params, function.param_types,
                function.return_type, function.token, lowered)


def verify_ir(program: ProgramIR) -> None:
    """Reject malformed CFG edges, misplaced terminators and stack states."""
    names = set()
    for function in program.functions:
        if function.name in names:
            raise BytecodeValidationError(f"IR duplicate function {function.name}")
        names.add(function.name)
        blocks = function.blocks
        if not blocks or blocks[0].original_offset != 0:
            raise BytecodeValidationError(f"{function.name}: missing entry block")
        labels = {b.label for b in blocks}
        if len(labels) != len(blocks):
            raise BytecodeValidationError(f"{function.name}: duplicate block label")
        if len(function.params) != len(function.param_types):
            raise BytecodeValidationError(f"{function.name}: invalid function signature")
        seen_offsets = set()
        for i, block in enumerate(blocks):
            if not block.instructions or block.original_offset in seen_offsets:
                raise BytecodeValidationError(f"{function.name}: empty or duplicate IR block")
            if i and block.original_offset <= blocks[i - 1].original_offset:
                raise BytecodeValidationError(f"{function.name}: unsorted blocks")
            seen_offsets.add(block.original_offset)
            if any(inst.op in _TERMINATORS for inst in block.instructions[:-1]):
                raise BytecodeValidationError(f"{function.name}: terminator inside block")
            last = block.instructions[-1]
            next_label = blocks[i + 1].label if i + 1 < len(blocks) else None
            outgoing = []
            if last.op in _JUMPS:
                if last.op != "JUMP" and next_label is not None:
                    outgoing.append(next_label)
                target = last.arg[1] if last.op == "BRANCH_FALSE" else last.arg
                if not isinstance(target, str):
                    raise BytecodeValidationError(f"{function.name}: invalid IR branch label")
                outgoing.append(target)
            elif last.op not in {"RETURN", "RETURN_VOID"} and next_label is not None:
                outgoing.append(next_label)
            if block.successors != _unique(outgoing):
                raise BytecodeValidationError(
                    f"{function.name}: invalid successors for {block.label}: "
                    f"expected {_unique(outgoing)}, got {block.successors}"
                )
            if any(label not in labels for label in block.successors):
                raise BytecodeValidationError(f"{function.name}: unknown successor in {block.label}")
        lowered = _lower_function(function)
        states = verify_function(lowered)
        offsets = {}
        position = 0
        for block in blocks:
            offsets[block.label] = position
            position += len(block.instructions)
        for block in blocks:
            expected = states.get(offsets[block.label])
            if expected != (block.entry_stack, block.entry_scopes):
                raise BytecodeValidationError(
                    f"{function.name}: invalid stack/scope state at {block.label}: "
                    f"{(block.entry_stack, block.entry_scopes)} vs {expected}"
                )
            if expected is None:
                raise BytecodeValidationError(f"{function.name}: unreachable IR block {block.label}")


def lower_ir(program: ProgramIR) -> Bytecode:
    """Convert validated IR to VM bytecode, compacting unreachable code."""
    verify_ir(program)
    bytecode = Bytecode(tuple(_lower_function(fn) for fn in program.functions))
    from .verify import verify_bytecode
    verify_bytecode(bytecode)
    return bytecode
