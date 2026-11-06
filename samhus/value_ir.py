"""Experimental stack-value IR with explicit producers, uses and join PHIs.

This converts verified stack CFG bytecode into named *stack* values, retaining
the source opcodes as opaque instructions for later native/compiler research.
Local mutable variables stay opaque LOAD/ASSIGN effects; this is NOT full SSA,
an independently executable backend, or a finalized language IR.
"""
from dataclasses import dataclass

from .bytecode import Instruction
from .ir import ProgramIR, compile_ir, verify_ir
from .parser import Program
from .typecheck import TypeChecker
from .typed_ir import analyze_ir, _step
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class ValueOp:
    offset: int
    instruction: Instruction
    inputs: tuple[str, ...]
    output: str | None
    output_type: str | None


@dataclass(frozen=True)
class ValuePhi:
    result: str
    type_name: str
    # predecessor label and outgoing stack identifier on that edge
    incoming: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ValueBlock:
    label: str
    predecessors: tuple[str, ...]
    successors: tuple[str, ...]
    entry_stack: tuple[str, ...]
    phis: tuple[ValuePhi, ...]
    operations: tuple[ValueOp, ...]
    exit_stack: tuple[str, ...]


@dataclass(frozen=True)
class ValueFunction:
    name: str
    blocks: tuple[ValueBlock, ...]


@dataclass(frozen=True)
class ValueProgram:
    cfg: ProgramIR
    functions: tuple[ValueFunction, ...]

    def disassemble(self) -> str:
        lines = []
        for fn in self.functions:
            lines.append(f"fn {fn.name}:")
            for block in fn.blocks:
                pred = ", ".join(block.predecessors) or "(entry)"
                succ = ", ".join(block.successors) or "(return)"
                lines.append(f"  {block.label}: predecessors={pred} -> {succ}")
                for phi in block.phis:
                    inc = ", ".join(f"{block}:{value}" for block, value in phi.incoming)
                    lines.append(f"    {phi.result}: {phi.type_name} = phi({inc})")
                for op in block.operations:
                    arg = "" if op.instruction.arg is None else " " + repr(op.instruction.arg)
                    result = (f"{op.output}: {op.output_type} = " if op.output else "")
                    used = (" (" + ", ".join(op.inputs) + ")") if op.inputs else ""
                    lines.append(
                        f"    {op.offset:04} {result}{op.instruction.op}{arg}{used}"
                        f" ; {op.instruction.token.line}:{op.instruction.token.column}"
                    )
                lines.append(f"    outgoing-stack={block.exit_stack!r}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def _pop(stack: list[str], count: int) -> tuple[str, ...]:
    if count < 0 or count > len(stack):
        raise BytecodeValidationError("Value IR stack underflow or invalid operand count")
    if not count:
        return ()
    items = tuple(stack[-count:])
    del stack[-count:]
    return items


def _operation(stack: list[str], ins: Instruction, value_id: str) -> tuple[tuple[str, ...], str | None]:
    op, arg = ins.op, ins.arg
    if op in {"PUSH", "LOAD"}:
        stack.append(value_id)
        return (), value_id
    if op in {"UNARY", "EXPECT_BOOL"}:
        operands = _pop(stack, 1)
        if op == "EXPECT_BOOL":
            stack.extend(operands)
            return operands, None
        stack.append(value_id)
        return operands, value_id
    if op in {"KEEP_FALSE", "KEEP_TRUE"}:
        if not stack:
            raise BytecodeValidationError("Value IR empty short-circuit stack")
        return (stack[-1],), None
    if op in {"BINARY", "INDEX"}:
        operands = _pop(stack, 2)
        stack.append(value_id)
        return operands, value_id
    if op in {"BUILD_LIST", "BUILD_MAP", "CALL"}:
        count = arg[1] if op == "CALL" else (2 * arg if op == "BUILD_MAP" else arg)
        operands = _pop(stack, count)
        stack.append(value_id)
        return operands, value_id
    if op in {"POP", "DECLARE", "ASSIGN", "RETURN", "BRANCH_FALSE"}:
        return _pop(stack, 1), None
    if op in {"TICK", "ASSERT_FRESH", "ASSERT_MUTABLE", "SCOPE_IN",
              "SCOPE_OUT", "JUMP", "RETURN_VOID"}:
        return (), None
    raise BytecodeValidationError(f"Value IR unsupported instruction {op!r}")


def _function(fn, types) -> ValueFunction:
    blocks = fn.blocks
    predecessors: dict[str, list[str]] = {block.label: [] for block in blocks}
    for block in blocks:
        for successor in block.successors:
            if block.label not in predecessors[successor]:
                predecessors[successor].append(block.label)

    # All value identifiers are deterministic based on CFG block and op
    # position. Multiple-predecessor stack slots reserve a stable PHI ID
    # even before their incoming loop backedges have been analyzed.
    entry: dict[str, tuple[str, ...]] = {blocks[0].label: ()}
    for block in blocks[1:]:
        if len(predecessors[block.label]) > 1:
            entry[block.label] = tuple(
                f"%{block.label}.phi{slot}" for slot in range(block.entry_stack)
            )

    states = dict(types)
    offset = 0
    offsets = {}
    for block in blocks:
        offsets[block.label] = offset
        offset += len(block.instructions)
    operations: dict[str, tuple[ValueOp, ...]] = {}
    exits: dict[str, tuple[str, ...]] = {}

    # The CFG is reachable from b0000. Cycles have a header with at least
    # two incoming edges; reserved PHIs break the data-flow dependency.
    pending = {block.label for block in blocks}
    for _ in range(len(blocks) + 1):
        if not pending:
            break
        progress = False
        for block in blocks:
            if block.label not in pending:
                continue
            label = block.label
            if label not in entry:
                preds = predecessors[label]
                if len(preds) != 1 or preds[0] not in exits:
                    continue
                entry[label] = exits[preds[0]]
            stack = list(entry[label])
            if len(stack) != block.entry_stack:
                raise BytecodeValidationError(f"{fn.name}: invalid value-stack entry at {label}")
            ops = []
            base = offsets[label]
            for index, instruction in enumerate(block.instructions):
                position = base + index
                before = states.get(position)
                if before is None:
                    raise BytecodeValidationError(f"{fn.name}: missing type state at {position}")
                symbolic = f"%{label}.v{index}"
                arguments, produced = _operation(stack, instruction, symbolic)
                typed_out = _step(before, instruction, {})
                output_type = typed_out.stack[-1] if produced else None
                # Function CALL type inference uses the full function table
                # in the real typed pass, below we refresh its type.
                if produced and instruction.op == "CALL":
                    if position + 1 in states:
                        next_stack = states[position + 1].stack
                        if next_stack:
                            output_type = next_stack[-1]
                ops.append(ValueOp(position, instruction, arguments, produced, output_type))
            exits[label] = tuple(stack)
            operations[label] = tuple(ops)
            pending.remove(label)
            progress = True
        if not progress:
            break
    if pending:
        raise BytecodeValidationError(
            f"{fn.name}: unresolved stack-value CFG blocks {sorted(pending)}"
        )

    value_blocks = []
    for block in blocks:
        preds = tuple(predecessors[block.label])
        phis = []
        if block.label != blocks[0].label and len(preds) > 1:
            for slot, target in enumerate(entry[block.label]):
                incoming = tuple((pred, exits[pred][slot]) for pred in preds)
                static_type = states[offsets[block.label]].stack[slot]
                phis.append(ValuePhi(target, static_type, incoming))
        value_blocks.append(ValueBlock(
            block.label, preds, block.successors, entry[block.label],
            tuple(phis), operations[block.label], exits[block.label],
        ))
    return ValueFunction(fn.name, tuple(value_blocks))


def _construct(cfg: ProgramIR) -> ValueProgram:
    typed = analyze_ir(cfg)
    return ValueProgram(
        cfg,
        tuple(_function(fn, states) for fn, states in zip(cfg.functions, typed.states)),
    )


def analyze_value_ir(cfg: ProgramIR) -> ValueProgram:
    verify_ir(cfg)
    result = _construct(cfg)
    verify_value_ir(result)
    return result


def compile_value_ir(program: Program) -> ValueProgram:
    TypeChecker(program).check()
    return analyze_value_ir(compile_ir(program))


def verify_value_ir(value_ir: ValueProgram) -> None:
    """Re-derive all value uses and PHI edges from verified CFG instructions.

    This reproducibility check rejects tampered input/output identifiers,
    altered predecessor lists, missing PHI sources or fabricated types.
    It is NOT an independent semantic proof or an untrusted IR decoder.
    """
    verify_ir(value_ir.cfg)
    try:
        expected = _construct(value_ir.cfg)
    except (KeyError, IndexError, TypeError) as exc:
        raise BytecodeValidationError(f"Invalid value-IR construction: {exc}") from None
    if value_ir.functions != expected.functions:
        raise BytecodeValidationError("Invalid value IR: definitions, uses or PHIs differ from CFG")
