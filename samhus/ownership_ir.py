"""Read-only String ownership obligations over verified stack Value IR.

This is a *planning* overlay, not executable retain/drop lowering. Value IR
tracks stack values but does not express aliasing in mutable locals, lifetimes
of function arguments, exceptions, or PHI edge ownership. No runtime can
safely consume this report as an instruction stream.
"""
from dataclasses import dataclass

from .value_ir import ValueProgram, verify_value_ir
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class OwnershipEvent:
    function: str
    block: str
    offset: int | None
    action: str
    value: str
    reason: str


@dataclass(frozen=True)
class OwnershipReport:
    events: tuple[OwnershipEvent, ...]
    blockers: tuple[str, ...]

    @property
    def safe_to_lower(self) -> bool:
        """Never authorize freeing/reusing storage with the present IR."""
        return False

    def disassemble(self) -> str:
        lines = ["String ownership obligations (ANALYSIS ONLY; no retain/drop emitted):"]
        for event in self.events:
            position = "edge" if event.offset is None else str(event.offset).zfill(4)
            lines.append(
                f"  {event.function}/{event.block} {position} "
                f"{event.action} {event.value}: {event.reason}"
            )
        if not self.events:
            lines.append("  (no String values in verified Value IR)")
        lines.append("  unresolved lifetime/cleanup gates:")
        if self.blockers:
            lines.extend(f"    - {item}" for item in self.blockers)
        else:
            lines.append("    - compiler ownership IR and exceptional cleanup unimplemented")
        lines.append("  safe_to_lower=false")
        return "\n".join(lines) + "\n"


def _plan(value: ValueProgram) -> OwnershipReport:
    events: list[OwnershipEvent] = []
    blockers: list[str] = []

    def note(message: str) -> None:
        if message not in blockers:
            blockers.append(message)

    for signature, function in zip(value.cfg.functions, value.functions):
        name = function.name
        for parameter, kind in zip(signature.params, signature.param_types):
            if kind == "String":
                note(f"{name}: String parameter {parameter!r} has no owned/borrowed ABI")
        types: dict[str, str | None] = {}
        for block in function.blocks:
            for phi in block.phis:
                types[phi.result] = phi.type_name
            for operation in block.operations:
                if operation.output is not None:
                    types[operation.output] = operation.output_type

        for block in function.blocks:
            for phi in block.phis:
                if phi.type_name == "String":
                    incoming = ", ".join(
                        f"{predecessor}:{source}"
                        for predecessor, source in phi.incoming
                    )
                    events.append(OwnershipEvent(
                        name, block.label, None, "PHI_EDGE_OWNER",
                        phi.result, f"incoming {incoming}",
                    ))
                    note(f"{name}: String PHI edge moves and cleanup are not modeled")

            for operation in block.operations:
                instruction = operation.instruction
                op = instruction.op
                offset = operation.offset
                if operation.output_type == "String" and operation.output is not None:
                    kind = {
                        "PUSH": "BORROW_STATIC_LITERAL",
                        "LOAD": "RETAIN_LOCAL_ON_LOAD",
                        "INDEX": "RETAIN_PARENT_FOR_SLICE",
                        "CALL": "RECEIVE_CALL_RESULT",
                    }.get(op)
                    if op == "BINARY" and instruction.arg == "+":
                        kind = "ALLOCATE_CONCAT_RESULT"
                    if kind is None:
                        kind = "UNRESOLVED_STRING_PRODUCER"
                        note(f"{name}: unsupported String producer {op!r}")
                    events.append(OwnershipEvent(
                        name, block.label, offset, kind, operation.output,
                        f"source operation {op}",
                    ))
                    if op == "LOAD":
                        note(f"{name}: LOAD of String local needs a retain/borrow contract")
                    if op == "CALL":
                        note(f"{name}: String call results need an owned-return contract")

                for source in operation.inputs:
                    if source not in types:
                        raise BytecodeValidationError(
                            f"Ownership analysis missing value type for {source!r}"
                        )
                    if types[source] != "String":
                        continue
                    if op in {"DECLARE", "ASSIGN"}:
                        action = "TRANSFER_OR_RETAIN_FOR_LOCAL"
                        note(
                            f"{name}: String locals need overwrite and scope-exit cleanup"
                        )
                    elif op == "RETURN":
                        action = "TRANSFER_RETURN_TO_CALLER"
                        note(
                            f"{name}: String returns need edge cleanup and transfer semantics"
                        )
                    elif op == "POP":
                        action = "DROP_UNUSED_TEMP"
                    elif op == "CALL":
                        action = "BORROW_CALL_ARGUMENT"
                        callee = instruction.arg[0]
                        if callee not in {"println", "len"}:
                            note(
                                f"{name}: call {callee!r} needs argument ownership contract"
                            )
                    elif op == "INDEX":
                        action = "BORROW_FOR_INDEX"
                    elif op == "BINARY":
                        action = "BORROW_FOR_BINARY"
                    else:
                        action = "UNRESOLVED_STRING_USE"
                        note(f"{name}: String input to {op!r} lacks ownership rule")
                    events.append(OwnershipEvent(
                        name, block.label, offset, action, source,
                        f"consumed by {op}",
                    ))

    return OwnershipReport(tuple(events), tuple(blockers))


def analyze_ownership_ir(value: ValueProgram) -> OwnershipReport:
    """Generate conservative obligations without mutating Value IR or runtime."""
    verify_value_ir(value)
    return _plan(value)


def verify_ownership_ir(value: ValueProgram, report: OwnershipReport) -> None:
    """Reject changed or missing obligations by deriving them from verified IR."""
    expected = analyze_ownership_ir(value)
    if type(report) is not OwnershipReport or report != expected:
        raise BytecodeValidationError(
            "Ownership IR report differs from verified Value IR"
        )
