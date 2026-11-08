"""Read-only String ownership obligations on CFG edges and normal exits.

This planner records which local store versions *would need* forwarding,
owner replacement, scope cleanup, or return cleanup in a future design.
It emits no retains/drops and does not cover temporary or exceptional
unwinding. No report here can authorize heap reclamation.
"""
from dataclasses import dataclass

from .local_lifetime_ir import analyze_local_lifetime_ir
from .local_ssa_ir import analyze_local_ssa_ir
from .value_ir import ValueProgram, verify_value_ir
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class OwnerEdge:
    function: str
    predecessor: str
    successor: str
    slot: str
    source_version: str
    target_version: str
    action: str


@dataclass(frozen=True)
class OwnerCleanup:
    function: str
    block: str
    offset: int
    action: str
    slot: str
    old_version: str
    new_version: str | None
    return_source: str | None


@dataclass(frozen=True)
class ExceptionGap:
    function: str
    block: str
    offset: int
    operation: str
    local_versions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class EdgeOwnershipReport:
    edges: tuple[OwnerEdge, ...]
    cleanups: tuple[OwnerCleanup, ...]
    exception_gaps: tuple[ExceptionGap, ...]

    @property
    def safe_to_lower(self) -> bool:
        return False

    def disassemble(self) -> str:
        lines = ["String CFG ownership obligations (RESEARCH; no releases emitted):"]
        for e in self.edges:
            lines.append(
                f"  {e.function} {e.predecessor}->{e.successor} "
                f"{e.action} {e.slot}: {e.source_version} => {e.target_version}"
            )
        for c in self.cleanups:
            tail = "" if c.new_version is None else f" -> {c.new_version}"
            escaped = "" if c.return_source is None else (
                f"; return stack source {c.return_source} must remain live"
            )
            lines.append(
                f"  {c.function}/{c.block} {c.offset:04} {c.action} "
                f"{c.slot}: {c.old_version}{tail}{escaped}"
            )
        for gap in self.exception_gaps:
            live = ", ".join(f"{slot}={version}" for slot, version in gap.local_versions)
            lines.append(
                f"  {gap.function}/{gap.block} {gap.offset:04} "
                f"UNMODELED_EXCEPTION_CLEANUP {gap.operation}: {live}"
            )
        if not (self.edges or self.cleanups or self.exception_gaps):
            lines.append("  (no local String owner obligations)")
        lines.append("  exceptional temporary/stack cleanup and alias rules unresolved")
        lines.append("  safe_to_lower=false")
        return "\n".join(lines) + "\n"


_RISKY = frozenset({
    "TICK", "ASSERT_FRESH", "ASSERT_MUTABLE", "CALL", "BINARY",
    "UNARY", "INDEX", "LOAD", "ASSIGN", "DECLARE", "BUILD_LIST",
    "BUILD_MAP", "PUSH",
})


def _one_function(signature, fn, ssa, lifetime):
    name = signature.name
    blocks = fn.blocks
    first = blocks[0].label
    local_events = {}
    for event in lifetime.events:
        if event.function == name and event.offset is not None:
            local_events.setdefault(event.offset, []).append(event)

    def slots_at(offset, action):
        return tuple(e.slot for e in local_events.get(offset, ())
                     if e.action == action)

    definitions = {
        (d.block, int(d.version[6:])): d
        for d in ssa.definitions if d.function == name
        and d.origin in {"DECLARE", "ASSIGN"}
    }
    phis = {
        (phi.block, phi.slot): phi
        for phi in ssa.phis if phi.function == name
    }
    params = {
        d.slot: d.version for d in ssa.definitions
        if d.function == name and d.origin == "PARAMETER"
    }
    outgoing = {}

    def start_state(block, partial=False):
        if block.label == first:
            return dict(params)
        if not partial and any(pred not in outgoing for pred in block.predecessors):
            raise BytecodeValidationError(
                f"{name}: incomplete owner edge at {block.label}"
            )
        parents = [outgoing[pred] for pred in block.predecessors if pred in outgoing]
        if not parents:
            return None
        keys = set(parents[0])
        if any(set(p) != keys for p in parents):
            if partial:
                return None
            raise BytecodeValidationError(
                f"{name}: mismatched owner slots at {block.label}"
            )
        state = {}
        for slot in sorted(keys):
            choices = {p[slot] for p in parents}
            phi = phis.get((block.label, slot))
            if phi is not None:
                state[slot] = phi.version
            elif len(choices) == 1:
                state[slot] = next(iter(choices))
            else:
                if partial:
                    return None
                raise BytecodeValidationError(
                    f"{name}: missing local String PHI at {block.label}"
                )
        return state

    def replay(block, initial, collect=False):
        state = dict(initial)
        cleanups = []
        gaps = []
        for op in block.operations:
            code, offset = op.instruction.op, op.offset
            if collect and code in _RISKY and state:
                gaps.append(ExceptionGap(
                    name, block.label, offset, code, tuple(sorted(state.items()))
                ))
            if code in {"DECLARE", "ASSIGN"}:
                definition = definitions.get((block.label, offset))
                if definition is not None:
                    old = state.get(definition.slot)
                    if code == "ASSIGN":
                        if old is None:
                            raise BytecodeValidationError(
                                f"{name}: owner replacement without active slot"
                            )
                        if collect:
                            cleanups.append(OwnerCleanup(
                                name, block.label, offset, "REPLACE_OWNER_OBLIGATION",
                                definition.slot, old, definition.version, None
                            ))
                    elif old is not None:
                        raise BytecodeValidationError(
                            f"{name}: duplicate owner declaration"
                        )
                    state[definition.slot] = definition.version
            elif code == "SCOPE_OUT":
                for slot in slots_at(offset, "RELEASE_STRING_AT_SCOPE_EXIT"):
                    if slot not in state:
                        raise BytecodeValidationError(
                            f"{name}: owner missing at scope exit"
                        )
                    version = state.pop(slot)
                    if collect:
                        cleanups.append(OwnerCleanup(
                            name, block.label, offset,
                            "SCOPE_EXIT_RELEASE_OBLIGATION",
                            slot, version, None, None
                        ))
            elif code in {"RETURN", "RETURN_VOID"}:
                return_source = op.inputs[0] if code == "RETURN" and op.inputs else None
                for slot in slots_at(offset, "RELEASE_STRING_AT_RETURN"):
                    if slot not in state:
                        raise BytecodeValidationError(
                            f"{name}: owner missing at return"
                        )
                    if collect:
                        cleanups.append(OwnerCleanup(
                            name, block.label, offset,
                            "RETURN_RELEASE_OBLIGATION", slot,
                            state[slot], None, return_source
                        ))
        return state, cleanups, gaps

    # Finite state: each slot carries one store/PHI version. Backedge PHIs
    # have deterministic labels, allowing bounded convergence.
    count_versions = len(definitions) + len(phis) + len(params) + 1
    max_passes = (len(blocks) + 1) * (count_versions + 2) * 2
    for _ in range(max_passes):
        updated = False
        for block in blocks:
            state = start_state(block, partial=True)
            if state is None:
                continue
            exit_state, _, _ = replay(block, state)
            if outgoing.get(block.label) != exit_state:
                outgoing[block.label] = exit_state
                updated = True
        if not updated and len(outgoing) == len(blocks):
            break
    else:
        raise BytecodeValidationError(
            f"{name}: owner edge versions did not converge"
        )

    edges, cleanups, gaps = [], [], []
    for block in blocks:
        entry = start_state(block)
        exit_state, releases, exceptional = replay(block, entry, collect=True)
        if outgoing[block.label] != exit_state:
            raise BytecodeValidationError(
                f"{name}: owner CFG fixed point changed"
            )
        cleanups.extend(releases)
        gaps.extend(exceptional)
        for successor in block.successors:
            target = next(b for b in blocks if b.label == successor)
            destination = start_state(target)
            if set(exit_state) != set(destination):
                raise BytecodeValidationError(
                    f"{name}: owner slot mismatch on CFG edge"
                )
            for slot, version in sorted(exit_state.items()):
                phi = phis.get((successor, slot))
                target_version = destination[slot]
                if phi is not None:
                    incoming = dict(phi.incoming)
                    if incoming.get(block.label) != version:
                        raise BytecodeValidationError(
                            f"{name}: owner PHI predecessor value mismatch"
                        )
                elif target_version != version:
                    raise BytecodeValidationError(
                        f"{name}: owner identity changed without PHI"
                    )
                edges.append(OwnerEdge(
                    name, block.label, successor, slot, version, target_version,
                    ("PHI_EDGE_OWNER_OBLIGATION" if phi is not None
                     else "FORWARD_STRING_LOCAL")
                ))
    return edges, cleanups, gaps


def _construct(value):
    local = analyze_local_lifetime_ir(value)
    ssa = analyze_local_ssa_ir(value)
    edges, cleanups, gaps = [], [], []
    for signature, fn in zip(value.cfg.functions, value.functions):
        part_edges, part_cleanups, part_gaps = _one_function(
            signature, fn, ssa, local
        )
        edges.extend(part_edges)
        cleanups.extend(part_cleanups)
        gaps.extend(part_gaps)
    return EdgeOwnershipReport(
        tuple(edges), tuple(cleanups), tuple(gaps)
    )


def analyze_edge_ownership_ir(value: ValueProgram) -> EdgeOwnershipReport:
    verify_value_ir(value)
    return _construct(value)


def verify_edge_ownership_ir(value: ValueProgram, report: EdgeOwnershipReport) -> None:
    """Reject tampered edge/cleanup inventories, without approving lowering."""
    expected = analyze_edge_ownership_ir(value)
    if type(report) is not EdgeOwnershipReport or report != expected:
        raise BytecodeValidationError(
            "String ownership edge obligations differ from verified Value IR"
        )
