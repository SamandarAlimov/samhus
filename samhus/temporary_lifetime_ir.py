"""Read-only String stack-temporary origins, uses and unwind gaps.

The report tracks named stack SSA values, NOT unique heap allocations.
A lexical last use does not authorize a drop: aliases, calls, slices,
String PHIs and exceptional unwinding remain unresolved.
"""
from dataclasses import dataclass

from .local_ssa_ir import analyze_local_ssa_ir
from .value_ir import ValueProgram, verify_value_ir
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class TemporaryOrigin:
    function: str
    block: str
    offset: int | None
    value: str
    kind: str
    inputs: tuple[str, ...]
    local_store: str | None


@dataclass(frozen=True)
class TemporaryUse:
    function: str
    block: str
    offset: int | None
    value: str
    action: str
    last_operation_use_in_block: bool
    successor: str | None = None


@dataclass(frozen=True)
class StackUnwindGap:
    function: str
    block: str
    offset: int
    operation: str
    live_string_temporaries: tuple[str, ...]


@dataclass(frozen=True)
class TemporaryLifetimeReport:
    origins: tuple[TemporaryOrigin, ...]
    uses: tuple[TemporaryUse, ...]
    unwind_gaps: tuple[StackUnwindGap, ...]

    @property
    def safe_to_lower(self) -> bool:
        return False

    def disassemble(self) -> str:
        lines = ["String stack temporary obligations (READ ONLY; no drop emitted):"]
        for origin in self.origins:
            position = "phi" if origin.offset is None else f"{origin.offset:04}"
            inputs = ",".join(origin.inputs) if origin.inputs else "-"
            store = f"; local-store {origin.local_store}" if origin.local_store else ""
            lines.append(
                f"  {origin.function}/{origin.block} {position} "
                f"{origin.value} {origin.kind} parents={inputs}{store}"
            )
        for use in self.uses:
            position = "edge" if use.offset is None else f"{use.offset:04}"
            edge = "" if use.successor is None else f" ->{use.successor}"
            last = " last-operation-use" if use.last_operation_use_in_block else ""
            lines.append(
                f"  {use.function}/{use.block} {position} "
                f"{use.action} {use.value}{edge}{last}"
            )
        for gap in self.unwind_gaps:
            lines.append(
                f"  {gap.function}/{gap.block} {gap.offset:04} "
                f"UNMODELED_STACK_UNWIND {gap.operation}: "
                f"{', '.join(gap.live_string_temporaries)}"
            )
        if not (self.origins or self.uses or self.unwind_gaps):
            lines.append("  (no typed String stack values)")
        lines.append("  last-operation-use is lexical only, never a memory-free proof")
        lines.append("  safe_to_lower=false")
        return "\n".join(lines) + "\n"


_RISKY_OPERATIONS = frozenset({
    "TICK", "CALL", "BINARY", "UNARY", "INDEX", "LOAD", "PUSH",
    "DECLARE", "ASSIGN", "ASSERT_FRESH", "ASSERT_MUTABLE",
    "BUILD_LIST", "BUILD_MAP",
})
_PRESERVE_TOP = frozenset({"KEEP_FALSE", "KEEP_TRUE", "EXPECT_BOOL"})


def _use_action(op: str) -> str:
    return {
        "DECLARE": "STORE_IN_LOCAL_OBLIGATION",
        "ASSIGN": "REPLACE_LOCAL_OBLIGATION",
        "RETURN": "ESCAPE_TO_CALLER",
        "POP": "DISCARD_RESULT_OBLIGATION",
        "CALL": "CALL_ARGUMENT_ABI_REQUIRED",
        "INDEX": "SLICE_PARENT_DEPENDENCY",
        "BINARY": "BINARY_OPERAND_BORROW",
    }.get(op, "UNRESOLVED_STRING_USE")


def _one_function(fn, reads):
    name = fn.name
    types = {}
    for block in fn.blocks:
        for phi in block.phis:
            types[phi.result] = phi.type_name
        for operation in block.operations:
            if operation.output is not None:
                types[operation.output] = operation.output_type

    def is_string(value):
        if value not in types:
            raise BytecodeValidationError(
                f"{name}: temporary references missing stack value {value!r}"
            )
        return types[value] == "String"

    local_reads = {
        r.offset: r.version for r in reads if r.function == name
    }
    origins = []
    kinds = {}
    for block in fn.blocks:
        for phi in block.phis:
            if phi.type_name == "String":
                sources = tuple(source for _, source in phi.incoming)
                if not all(is_string(source) for source in sources):
                    raise BytecodeValidationError(
                        f"{name}: incompatible String stack PHI"
                    )
                origin = TemporaryOrigin(
                    name, block.label, None, phi.result, "STACK_PHI",
                    sources, None,
                )
                origins.append(origin)
                kinds[phi.result] = origin.kind
        for op in block.operations:
            if op.output is None or op.output_type != "String":
                continue
            opcode = op.instruction.op
            kind = {
                "PUSH": "STATIC_LITERAL",
                "LOAD": "LOCAL_LOAD_ALIAS",
                "INDEX": "PARENT_DEPENDENT_VIEW",
                "CALL": "CALL_RESULT_UNKNOWN_ABI",
            }.get(opcode, "UNKNOWN_STRING_PRODUCER")
            if opcode == "BINARY" and op.instruction.arg == "+":
                kind = "CONCAT_RESULT"
            local_store = None
            if opcode == "LOAD":
                local_store = local_reads.get(op.offset)
                if local_store is None:
                    raise BytecodeValidationError(
                        f"{name}: String load has no resolved local store version"
                    )
            origin = TemporaryOrigin(
                name, block.label, op.offset, op.output, kind,
                tuple(item for item in op.inputs if is_string(item)),
                local_store,
            )
            origins.append(origin)
            kinds[op.output] = kind

    uses = []
    gaps = []
    for block in fn.blocks:
        stack = list(block.entry_stack)
        remaining = {}
        for op in block.operations:
            for source in op.inputs:
                if is_string(source):
                    remaining[source] = remaining.get(source, 0) + 1
        for op in block.operations:
            opcode = op.instruction.op
            # Stack is sampled before the operation. A failing operation
            # can strand already-created temporaries on the evaluation stack.
            if opcode in _RISKY_OPERATIONS:
                live = tuple(
                    item for item in stack
                    if is_string(item) and kinds.get(item) != "STATIC_LITERAL"
                )
                if live:
                    gaps.append(StackUnwindGap(
                        name, block.label, op.offset, opcode, live
                    ))

            for source in op.inputs:
                if is_string(source):
                    remaining[source] -= 1
                    uses.append(TemporaryUse(
                        name, block.label, op.offset, source,
                        _use_action(opcode), remaining[source] == 0,
                    ))

            if opcode in _PRESERVE_TOP:
                if not stack or tuple(stack[-1:]) != op.inputs:
                    raise BytecodeValidationError(
                        f"{name}: inconsistent preserved Value IR stack"
                    )
            elif op.inputs:
                count = len(op.inputs)
                if count > len(stack) or tuple(stack[-count:]) != op.inputs:
                    raise BytecodeValidationError(
                        f"{name}: inconsistent temporary stack operands"
                    )
                del stack[-count:]
            if op.output is not None:
                stack.append(op.output)
        if tuple(stack) != block.exit_stack:
            raise BytecodeValidationError(
                f"{name}: inconsistent outgoing temporary stack"
            )

    # A PHI edge reads the predecessor's outgoing stack value. Its use
    # is conditional on that CFG edge, not a globally unique last use.
    for block in fn.blocks:
        for phi in block.phis:
            if phi.type_name != "String":
                continue
            for predecessor, source in phi.incoming:
                uses.append(TemporaryUse(
                    name, predecessor, None, source,
                    "STACK_PHI_EDGE_FORWARD", False, block.label
                ))
    return origins, uses, gaps


def _construct(value: ValueProgram) -> TemporaryLifetimeReport:
    local = analyze_local_ssa_ir(value)
    origins, uses, gaps = [], [], []
    for fn in value.functions:
        function_origins, function_uses, function_gaps = _one_function(
            fn, local.reads
        )
        origins.extend(function_origins)
        uses.extend(function_uses)
        gaps.extend(function_gaps)
    return TemporaryLifetimeReport(
        tuple(origins), tuple(uses), tuple(gaps)
    )


def analyze_temporary_lifetime_ir(value: ValueProgram) -> TemporaryLifetimeReport:
    verify_value_ir(value)
    return _construct(value)


def verify_temporary_lifetime_ir(
        value: ValueProgram, report: TemporaryLifetimeReport) -> None:
    """Rebuild a verified source graph and reject changed temporary facts."""
    expected = analyze_temporary_lifetime_ir(value)
    if type(report) is not TemporaryLifetimeReport or report != expected:
        raise BytecodeValidationError(
            "String temporary lifetime report differs from verified Value IR"
        )
