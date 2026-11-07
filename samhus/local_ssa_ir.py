"""Research-only local String store-version / PHI graph.

This is a named *store* data-flow overlay, not a complete owned-value SSA:
the graph has no independent dominance proof, alias/escape semantics,
exceptional cleanup, retain/drop emission or safe native lowering.
"""
from dataclasses import dataclass

from .local_lifetime_ir import analyze_local_lifetime_ir
from .value_ir import ValueProgram, verify_value_ir
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class LocalSSADef:
    function: str
    block: str
    slot: str
    version: str
    origin: str
    source: str | None
    previous: str | None


@dataclass(frozen=True)
class LocalSSARead:
    function: str
    block: str
    slot: str
    offset: int
    version: str


@dataclass(frozen=True)
class LocalSSAPhi:
    function: str
    block: str
    slot: str
    version: str
    incoming: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class LocalSSAReport:
    definitions: tuple[LocalSSADef, ...]
    reads: tuple[LocalSSARead, ...]
    phis: tuple[LocalSSAPhi, ...]

    @property
    def safe_to_lower(self) -> bool:
        return False

    def disassemble(self) -> str:
        lines = ["Local String store versions (RESEARCH ONLY; no ownership codegen):"]
        for item in self.definitions:
            origin = item.origin
            if item.previous is not None:
                origin += f" replaces {item.previous}"
            lines.append(
                f"  {item.function}/{item.block} {item.version} "
                f"= {origin} {item.slot} from {item.source or '(parameter)'}"
            )
        for phi in self.phis:
            incoming = ", ".join(
                f"{pred}:{name}" for pred, name in phi.incoming
            )
            lines.append(
                f"  {phi.function}/{phi.block} {phi.version} "
                f"= phi({incoming}) for {phi.slot}"
            )
        for read in self.reads:
            lines.append(
                f"  {read.function}/{read.block} {read.offset:04} "
                f"load {read.slot} from {read.version}"
            )
        if not (self.definitions or self.reads or self.phis):
            lines.append("  (no local String definitions or reads)")
        lines.append("  safe_to_lower=false")
        return "\n".join(lines) + "\n"


def _event_lookup(function, events):
    offset_events = {}
    for event in events:
        if event.function == function and event.offset is not None:
            offset_events.setdefault(event.offset, []).append(event)
    return offset_events


def _analyze_function(signature, function, events):
    name = signature.name
    blocks = function.blocks
    by_offset = _event_lookup(name, events)
    names = {
        "BIND_STRING_LOCAL", "REPLACE_STRING_LOCAL_OWNER",
        "READ_STRING_LOCAL_STORE", "RELEASE_STRING_AT_SCOPE_EXIT",
    }
    for found in by_offset.values():
        for item in found:
            if item.action not in names and item.action != "RELEASE_STRING_AT_RETURN":
                raise BytecodeValidationError(
                    f"{name}: unexpected String lifetime event {item.action}"
                )

    def matching(offset, action):
        return [event for event in by_offset.get(offset, ())
                if event.action == action]

    initial = {
        f"arg:{index}": f"%arg{index}"
        for index, kind in enumerate(signature.param_types) if kind == "String"
    }
    versions = {}
    for block in blocks:
        for op in block.operations:
            if op.instruction.op in {"DECLARE", "ASSIGN"}:
                action = ("BIND_STRING_LOCAL" if op.instruction.op == "DECLARE"
                          else "REPLACE_STRING_LOCAL_OWNER")
                found = matching(op.offset, action)
                if len(found) > 1:
                    raise BytecodeValidationError(f"{name}: repeated String write")
                if found:
                    versions[op.offset] = (found[0].slot, f"%store{op.offset}")

    out = {}

    def incoming(block, known, require_all=False):
        if block.label == blocks[0].label:
            return dict(initial)
        if require_all and any(predecessor not in known for predecessor in block.predecessors):
            raise BytecodeValidationError(f"{name}: missing SSA predecessor")
        parents = [(pred, known[pred]) for pred in block.predecessors if pred in known]
        if not parents:
            return None
        slots = set(parents[0][1])
        if any(set(state) != slots for _pred, state in parents):
            # A verified lexical CFG should not join incompatible active
            # String slots. Incomplete data-flow passes can be retried.
            if require_all:
                raise BytecodeValidationError(f"{name}: inconsistent String slots at join")
            return None
        merged = {}
        for slot in sorted(slots):
            values = [state[slot] for _pred, state in parents]
            merged[slot] = (
                values[0] if all(value == values[0] for value in values)
                else f"%{block.label}.local_{slot.replace(':', '_')}"
            )
        return merged

    def simulate(block, state, collect=False):
        current = dict(state)
        definitions, reads = [], []
        for op in block.operations:
            code = op.instruction.op
            if op.offset in versions:
                slot, version = versions[op.offset]
                previous = current.get(slot)
                if code == "ASSIGN" and previous is None:
                    raise BytecodeValidationError(
                        f"{name}: String assignment without current SSA store"
                    )
                current[slot] = version
                if collect:
                    definitions.append(LocalSSADef(
                        name, block.label, slot, version, code,
                        op.inputs[0] if op.inputs else None, previous,
                    ))
            elif code == "LOAD":
                found = matching(op.offset, "READ_STRING_LOCAL_STORE")
                if found:
                    if len(found) != 1:
                        raise BytecodeValidationError(
                            f"{name}: duplicate String read"
                        )
                    slot = found[0].slot
                    if slot not in current:
                        raise BytecodeValidationError(
                            f"{name}: String read without current SSA store"
                        )
                    if collect:
                        reads.append(LocalSSARead(
                            name, block.label, slot, op.offset, current[slot]
                        ))
            elif code == "SCOPE_OUT":
                for event in matching(op.offset, "RELEASE_STRING_AT_SCOPE_EXIT"):
                    if event.slot not in current:
                        raise BytecodeValidationError(
                            f"{name}: String scope exit without current SSA store"
                        )
                    del current[event.slot]
        return current, definitions, reads

    # Loop headers can have an initially unknown backedge. The PHI name is
    # deterministic and permits fixed-point iteration without source values
    # being executable. Every pass is bounded by finite store IDs/CFG blocks.
    max_passes = (len(blocks) + 1) * (len(versions) + 3) * 2
    for _ in range(max_passes):
        modified = False
        for block in blocks:
            merged = incoming(block, out)
            if merged is None:
                continue
            new_state, _, _ = simulate(block, merged)
            if out.get(block.label) != new_state:
                out[block.label] = new_state
                modified = True
        if not modified and len(out) == len(blocks):
            break
    else:
        raise BytecodeValidationError(f"{name}: local SSA did not converge")

    defs = [
        LocalSSADef(name, blocks[0].label, slot, version, "PARAMETER", None, None)
        for slot, version in sorted(initial.items())
    ]
    reads, phis = [], []
    for block in blocks:
        merged = incoming(block, out, require_all=True)
        for slot, version in sorted(merged.items()):
            if version.startswith(f"%{block.label}.local_"):
                phis.append(LocalSSAPhi(
                    name, block.label, slot, version,
                    tuple((pred, out[pred][slot]) for pred in block.predecessors),
                ))
        final, writes, loaded = simulate(block, merged, collect=True)
        if final != out[block.label]:
            raise BytecodeValidationError(f"{name}: unstable local SSA fixed point")
        defs.extend(writes)
        reads.extend(loaded)
    return defs, reads, phis


def _construct(value: ValueProgram) -> LocalSSAReport:
    lifetime = analyze_local_lifetime_ir(value)
    definitions, reads, phis = [], [], []
    for signature, function in zip(value.cfg.functions, value.functions):
        defs, loads, joins = _analyze_function(
            signature, function, lifetime.events
        )
        definitions.extend(defs)
        reads.extend(loads)
        phis.extend(joins)
    return LocalSSAReport(
        tuple(definitions), tuple(reads), tuple(phis)
    )


def analyze_local_ssa_ir(value: ValueProgram) -> LocalSSAReport:
    verify_value_ir(value)
    return _construct(value)


def verify_local_ssa_ir(value: ValueProgram, report: LocalSSAReport) -> None:
    """Reject changed definition/read/edge inventories via reconstruction."""
    expected = analyze_local_ssa_ir(value)
    if type(report) is not LocalSSAReport or report != expected:
        raise BytecodeValidationError(
            "Local String SSA report differs from verified Value IR"
        )
