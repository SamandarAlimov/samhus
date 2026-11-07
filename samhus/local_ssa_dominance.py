"""Independent CFG dominance and def-use checks for local String store SSA.

Validates graph topology without rebuilding the reaching-store solution.
This is NOT ownership, alias, exceptional cleanup, or native lowering proof.
"""
from dataclasses import dataclass

from .value_ir import ValueProgram, verify_value_ir
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class DefinitionSite:
    block: str
    offset: int  # -1 for parameters and block-entry PHIs
    slot: str


def compute_dominators(function) -> dict[str, frozenset[str]]:
    """Compute block dominators from verified Value CFG predecessors."""
    blocks = function.blocks
    if not blocks:
        raise BytecodeValidationError("Cannot dominate an empty CFG")
    labels = {block.label for block in blocks}
    root = blocks[0].label
    dom = {label: ({root} if label == root else set(labels)) for label in labels}
    for _ in range(len(labels) * len(labels) + 1):
        changed = False
        for block in blocks[1:]:
            preds = block.predecessors
            if not preds or any(pred not in dom for pred in preds):
                raise BytecodeValidationError(
                    f"Invalid dominance predecessors at {block.label}"
                )
            common = set(labels)
            for pred in preds:
                common.intersection_update(dom[pred])
            next_dom = common | {block.label}
            if next_dom != dom[block.label]:
                dom[block.label] = next_dom
                changed = True
        if not changed:
            return {label: frozenset(value) for label, value in dom.items()}
    raise BytecodeValidationError("Dominance analysis failed to converge")


def verify_local_ssa_dominance(value: ValueProgram, report) -> None:
    """Check SSA definition availability, correct PHI edges and use order.

    Independent of SSA report reconstruction. Does not establish memory safety.
    """
    verify_value_ir(value)
    signatures = {signature.name: signature for signature in value.cfg.functions}
    functions = {function.name: function for function in value.functions}
    for item in (*report.definitions, *report.reads, *report.phis):
        if item.function not in functions:
            raise BytecodeValidationError(
                f"Local SSA graph refers to missing function {item.function!r}"
            )

    for name, function in functions.items():
        signature = signatures[name]
        blocks = {block.label: block for block in function.blocks}
        dom = compute_dominators(function)
        operations = {
            (block.label, op.offset): op
            for block in function.blocks for op in block.operations
        }
        site: dict[str, DefinitionSite] = {}

        def define(version: str, block: str, offset: int, slot: str) -> None:
            if block not in blocks:
                raise BytecodeValidationError(f"{name}: definition in unknown block")
            if version in site:
                raise BytecodeValidationError(
                    f"{name}: duplicate SSA definition {version!r}"
                )
            site[version] = DefinitionSite(block, offset, slot)

        definitions = [d for d in report.definitions if d.function == name]
        phis = [p for p in report.phis if p.function == name]
        reads = [r for r in report.reads if r.function == name]

        for item in definitions:
            if item.origin == "PARAMETER":
                if not item.version.startswith("%arg"):
                    raise BytecodeValidationError(f"{name}: invalid parameter SSA ID")
                numeric = item.version[4:]
                if (not numeric.isascii() or not numeric.isdecimal()
                        or len(numeric) > 5 or str(int(numeric)) != numeric):
                    raise BytecodeValidationError(f"{name}: invalid parameter index")
                index = int(numeric)
                if (index >= len(signature.params)
                        or signature.param_types[index] != "String"
                        or item.slot != f"arg:{index}"
                        or item.block != function.blocks[0].label
                        or item.previous is not None
                        or item.source is not None):
                    raise BytecodeValidationError(f"{name}: malformed String parameter")
                define(item.version, item.block, -1, item.slot)
            elif item.origin in {"DECLARE", "ASSIGN"}:
                if not item.version.startswith("%store"):
                    raise BytecodeValidationError(f"{name}: invalid store SSA ID")
                numeric = item.version[6:]
                if (not numeric.isascii() or not numeric.isdecimal()
                        or len(numeric) > 12 or str(int(numeric)) != numeric):
                    raise BytecodeValidationError(f"{name}: invalid store offset")
                offset = int(numeric)
                op = operations.get((item.block, offset))
                if (op is None or op.instruction.op != item.origin
                        or len(op.inputs) != 1 or item.source != op.inputs[0]):
                    raise BytecodeValidationError(f"{name}: forged store SSA definition")
                if item.origin == "DECLARE" and (
                        item.slot != f"local:{offset}" or item.previous is not None):
                    raise BytecodeValidationError(f"{name}: invalid local declaration SSA")
                define(item.version, item.block, offset, item.slot)
            else:
                raise BytecodeValidationError(f"{name}: invalid SSA origin {item.origin}")

        for phi in phis:
            if phi.block not in blocks:
                raise BytecodeValidationError(f"{name}: PHI in unknown block")
            block = blocks[phi.block]
            if (len(block.predecessors) < 2
                    or phi.version != f"%{block.label}.local_{phi.slot.replace(':', '_')}"
                    or tuple(pred for pred, _src in phi.incoming)
                    != block.predecessors):
                raise BytecodeValidationError(
                    f"{name}: invalid local String PHI predecessor edges"
                )
            define(phi.version, phi.block, -1, phi.slot)

        def available(version: str, slot: str, target_block: str,
                      target_offset: int | None) -> None:
            definition = site.get(version)
            if definition is None:
                raise BytecodeValidationError(
                    f"{name}: String SSA use of undefined version {version!r}"
                )
            if definition.slot != slot:
                raise BytecodeValidationError(
                    f"{name}: String SSA use crosses lexical slots"
                )
            if definition.block == target_block:
                if (target_offset is not None
                        and definition.offset >= target_offset):
                    raise BytecodeValidationError(
                        f"{name}: String SSA use before local definition"
                    )
            elif definition.block not in dom[target_block]:
                raise BytecodeValidationError(
                    f"{name}: String SSA definition does not dominate use/edge"
                )

        for item in definitions:
            if item.origin == "ASSIGN":
                if item.previous is None:
                    raise BytecodeValidationError(
                        f"{name}: String SSA assignment has no previous version"
                    )
                available(
                    item.previous, item.slot, item.block,
                    site[item.version].offset
                )

        for read in reads:
            op = operations.get((read.block, read.offset))
            if op is None or op.instruction.op != "LOAD":
                raise BytecodeValidationError(
                    f"{name}: String SSA read at non-LOAD instruction"
                )
            available(read.version, read.slot, read.block, read.offset)

        for phi in phis:
            for predecessor, source in phi.incoming:
                # Read the incoming version at the end of predecessor,
                # permitting a predecessor-local write on that edge.
                available(source, phi.slot, predecessor, None)
