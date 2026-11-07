"""Read-only lexical String lifetime and reaching-store analysis for Value IR.

This overlay deliberately does NOT schedule executable retain/drop instructions.
Bindings are lexical slots, NOT SSA values. Reaching stores form conservative
may-sets across branches/loops; there is no alias, escape, or error cleanup
proof, so an ownership-lowering backend must not consume these as instructions.
"""
from dataclasses import dataclass

from .value_ir import ValueProgram, verify_value_ir
from .verify import BytecodeValidationError


@dataclass(frozen=True)
class LocalBinding:
    slot: str
    name: str
    type_name: str
    parameter: bool = False


@dataclass(frozen=True)
class LocalLifetimeEvent:
    function: str
    block: str
    offset: int | None
    action: str
    slot: str
    detail: str


@dataclass(frozen=True)
class LocalLifetimeReport:
    events: tuple[LocalLifetimeEvent, ...]
    blockers: tuple[str, ...]


def _analyze_function(signature, fn):
    types = {}
    for block in fn.blocks:
        for phi in block.phis:
            types[phi.result] = phi.type_name
        for op in block.operations:
            if op.output is not None:
                types[op.output] = op.output_type

    params = tuple(
        LocalBinding(f"arg:{index}", name, kind or "Any", True)
        for index, (name, kind) in enumerate(
            zip(signature.params, signature.param_types)
        )
    )
    blocks = {block.label: block for block in fn.blocks}
    first = fn.blocks[0].label
    in_scopes = {first: (params,)}
    todo = [first]
    resolved = {}
    leaving = {}
    returns = {}

    def find(scopes, name):
        for scope in reversed(scopes):
            for binding in reversed(scope):
                if binding.name == name:
                    return binding
        return None

    # One finite, structural analysis: lexical identity does not depend on
    # reaching store values, and scopes must agree at all CFG joins.
    while todo:
        label = todo.pop()
        scopes = [list(layer) for layer in in_scopes[label]]
        for op in blocks[label].operations:
            instruction = op.instruction
            code, arg = instruction.op, instruction.arg
            if code == "SCOPE_IN":
                scopes.append([])
            elif code == "SCOPE_OUT":
                if len(scopes) < 2:
                    raise BytecodeValidationError(
                        f"{signature.name}: local lifetime scope underflow"
                    )
                leaving[op.offset] = tuple(reversed(scopes.pop()))
            elif code == "DECLARE":
                name, _mutable, declared = arg
                if any(binding.name == name for binding in scopes[-1]):
                    raise BytecodeValidationError(
                        f"{signature.name}: duplicate local lifetime binding {name!r}"
                    )
                inferred = types.get(op.inputs[0], "Any") if op.inputs else "Any"
                binding = LocalBinding(
                    f"local:{op.offset}", name, declared or inferred or "Any"
                )
                scopes[-1].append(binding)
                resolved[op.offset] = binding
            elif code in {"LOAD", "ASSIGN"}:
                binding = find(scopes, arg)
                if binding is None:
                    raise BytecodeValidationError(
                        f"{signature.name}: unresolved local lifetime binding {arg!r}"
                    )
                previous = resolved.get(op.offset)
                if previous is not None and previous != binding:
                    raise BytecodeValidationError(
                        f"{signature.name}: inconsistent binding across control-flow paths"
                    )
                resolved[op.offset] = binding
            elif code in {"RETURN", "RETURN_VOID"}:
                returns[op.offset] = tuple(
                    binding for layer in scopes for binding in layer
                    if not binding.parameter
                )
        exit_state = tuple(tuple(layer) for layer in scopes)
        for successor in blocks[label].successors:
            previous = in_scopes.get(successor)
            if previous is None:
                in_scopes[successor] = exit_state
                todo.append(successor)
            elif previous != exit_state:
                raise BytecodeValidationError(
                    f"{signature.name}: different lexical bindings at {successor}"
                )
    if len(in_scopes) != len(fn.blocks):
        raise BytecodeValidationError(
            f"{signature.name}: missing lexical lifetime CFG blocks"
        )

    # Monotone forward may-reaching-store sets. Loop backedges converge
    # because the finite universe consists only of parameter/statement IDs.
    entry_reaching = {
        binding.slot: frozenset((f"param@{binding.slot}",))
        for binding in params if binding.type_name == "String"
    }
    outgoing = {}

    def transfer(block, initial):
        reach = {key: frozenset(vals) for key, vals in initial.items()}
        for op in block.operations:
            code = op.instruction.op
            if code == "DECLARE":
                binding = resolved[op.offset]
                if binding.type_name == "String":
                    reach[binding.slot] = frozenset((f"declare@{op.offset}",))
            elif code == "ASSIGN":
                binding = resolved[op.offset]
                if binding.type_name == "String":
                    reach[binding.slot] = frozenset((f"assign@{op.offset}",))
            elif code == "SCOPE_OUT":
                for binding in leaving[op.offset]:
                    reach.pop(binding.slot, None)
        return reach

    limit = len(fn.blocks) * (
        3 + sum(op.instruction.op in {"DECLARE", "ASSIGN"}
                for block in fn.blocks for op in block.operations)
    )
    for _ in range(limit):
        changed = False
        for block in fn.blocks:
            if block.label != first:
                parent_values = [outgoing[parent] for parent in block.predecessors
                                 if parent in outgoing]
                if not parent_values:
                    continue
                incoming = {}
                for source in parent_values:
                    for slot, values in source.items():
                        incoming[slot] = incoming.get(slot, frozenset()) | values
            else:
                incoming = entry_reaching
            output = transfer(block, incoming)
            if outgoing.get(block.label) != output:
                outgoing[block.label] = output
                changed = True
        if not changed and len(outgoing) == len(fn.blocks):
            break
    else:
        raise BytecodeValidationError(
            f"{signature.name}: reaching-store analysis failed to converge"
        )

    events = []
    blockers = []

    def blocked(message):
        if message not in blockers:
            blockers.append(message)

    for block in fn.blocks:
        if block.label == first:
            incoming = dict(entry_reaching)
        else:
            incoming = {}
            for predecessor in block.predecessors:
                for slot, values in outgoing[predecessor].items():
                    incoming[slot] = incoming.get(slot, frozenset()) | values
        reach = dict(incoming)
        for binding in (binding for layer in in_scopes[block.label]
                        for binding in layer if binding.type_name == "String"):
            versions = reach.get(binding.slot, frozenset())
            if len(block.predecessors) > 1 and len(versions) > 1:
                events.append(LocalLifetimeEvent(
                    signature.name, block.label, None,
                    "JOIN_STRING_REACHING_STORES", binding.slot,
                    ", ".join(sorted(versions)),
                ))
                blocked(f"{signature.name}: {binding.slot} joins multiple String stores")

        for op in block.operations:
            code = op.instruction.op
            if code == "DECLARE":
                binding = resolved[op.offset]
                if binding.type_name == "String":
                    events.append(LocalLifetimeEvent(
                        signature.name, block.label, op.offset,
                        "BIND_STRING_LOCAL", binding.slot,
                        f"name={binding.name!r}; source={op.inputs!r}",
                    ))
                    reach[binding.slot] = frozenset((f"declare@{op.offset}",))
            elif code == "LOAD":
                binding = resolved[op.offset]
                if binding.type_name == "String":
                    versions = reach.get(binding.slot, frozenset())
                    if not versions:
                        raise BytecodeValidationError(
                            f"{signature.name}: String load without reaching store"
                        )
                    events.append(LocalLifetimeEvent(
                        signature.name, block.label, op.offset,
                        "READ_STRING_LOCAL_STORE", binding.slot,
                        ", ".join(sorted(versions)),
                    ))
            elif code == "ASSIGN":
                binding = resolved[op.offset]
                if binding.type_name == "String":
                    versions = reach.get(binding.slot, frozenset())
                    events.append(LocalLifetimeEvent(
                        signature.name, block.label, op.offset,
                        "REPLACE_STRING_LOCAL_OWNER", binding.slot,
                        f"old={','.join(sorted(versions)) or '(none)'}; "
                        f"new={op.inputs!r}",
                    ))
                    blocked(
                        f"{signature.name}: String rebind needs retain-before-drop "
                        f"and exceptional cleanup"
                    )
                    reach[binding.slot] = frozenset((f"assign@{op.offset}",))
            elif code == "SCOPE_OUT":
                for binding in leaving[op.offset]:
                    reach.pop(binding.slot, None)
                    if binding.type_name == "String":
                        events.append(LocalLifetimeEvent(
                            signature.name, block.label, op.offset,
                            "RELEASE_STRING_AT_SCOPE_EXIT", binding.slot,
                            f"name={binding.name!r}",
                        ))
                        blocked(
                            f"{signature.name}: scope release needs proven ownership"
                        )
            elif code in {"RETURN", "RETURN_VOID"}:
                for binding in reversed(returns[op.offset]):
                    if binding.type_name == "String":
                        events.append(LocalLifetimeEvent(
                            signature.name, block.label, op.offset,
                            "RELEASE_STRING_AT_RETURN", binding.slot,
                            f"name={binding.name!r}; preserve returned aliases",
                        ))
                        blocked(
                            f"{signature.name}: return cleanup must preserve "
                            f"escaping aliases"
                        )
    return events, blockers


def analyze_local_lifetime_ir(value: ValueProgram) -> LocalLifetimeReport:
    """Analyze lexical identities and may-reaching writes; never emit C code."""
    verify_value_ir(value)
    events = []
    blockers = []
    for signature, function in zip(value.cfg.functions, value.functions):
        function_events, function_blockers = _analyze_function(signature, function)
        events.extend(function_events)
        for reason in function_blockers:
            if reason not in blockers:
                blockers.append(reason)
    return LocalLifetimeReport(tuple(events), tuple(blockers))
