"""Experimental Value IR -> C11 backend for scoped Int64/Bool programs.

Handles basic local variables and loops without rewriting the source AST to
C. Only the restricted typed Int/Bool subset is compiled; this remains a
research backend, not full language parity, formal SSA or a safe sandbox.
"""
from .errors import SamhusError
from .native_c import MAX_INT, PRELUDE
from .parser import Program
from .value_ir import ValueProgram, compile_value_ir, verify_value_ir


def _fail(instruction, reason: str):
    raise SamhusError(
        "Native Value IR subset: " + reason,
        instruction.token.line, instruction.token.column,
    )


def _symbol(identifier: str) -> str:
    # Values originate only from compiler-generated block labels.
    if not identifier.startswith("%") or not all(
            char.isascii() and (char.isalnum() or char in "._")
            for char in identifier[1:]):
        raise ValueError("Invalid generated Value IR identifier")
    return "shv_" + identifier[1:].replace(".", "_")


def _emit_edge(lines: list[str], predecessor: str, target: str, blocks) -> None:
    """Parallel PHI moves on a CFG edge; staging avoids register swaps."""
    if target not in blocks:
        raise ValueError("Invalid native Value IR successor")
    phis = blocks[target].phis
    incoming = []
    for phi in phis:
        matched = [value for parent, value in phi.incoming if parent == predecessor]
        if len(matched) != 1:
            raise ValueError("Invalid native Value IR PHI predecessor")
        incoming.append((phi.result, matched[0]))
    lines.append("    {")
    for index, (_, source) in enumerate(incoming):
        lines.append(f"        int64_t sh_move_{index} = {_symbol(source)};")
    for index, (destination, _) in enumerate(incoming):
        lines.append(f"        {_symbol(destination)} = sh_move_{index};")
    lines.append(f"        goto shb_{target};")
    lines.append("    }")



def _collect_locals(function, types):
    """Resolve locals using bytecode's lexical SCOPE_IN/OUT order.

    An individual source DECLARE has a unique hoisted C cell, even if the
    variable is shadowed. Cells are overwritten on each loop iteration.
    This deliberately does not claim mutable locals have become SSA values.
    """
    scopes = [{}]
    resolved = {}
    variables = []
    for block in function.blocks:
        for operation in block.operations:
            instruction = operation.instruction
            op, arg = instruction.op, instruction.arg
            if op == "SCOPE_IN":
                scopes.append({})
            elif op == "SCOPE_OUT":
                if len(scopes) <= 1:
                    _fail(instruction, "scope underflow")
                scopes.pop()
            elif op == "DECLARE":
                name, mutable, annotation = arg
                if name in scopes[-1]:
                    _fail(instruction, f"duplicate declaration {name!r}")
                kind = annotation or types[operation.inputs[0]]
                if kind not in {"Int", "Bool"}:
                    _fail(instruction, f"unsupported declared type {kind!r}")
                identifier = f"sh_local_{len(variables)}"
                scopes[-1][name] = (identifier, kind, mutable)
                variables.append(identifier)
                resolved[operation.offset] = scopes[-1][name]
            elif op in {"LOAD", "ASSIGN", "ASSERT_MUTABLE", "ASSERT_FRESH"}:
                if op == "ASSERT_FRESH":
                    if arg in scopes[-1]:
                        _fail(instruction, f"duplicate declaration {arg!r}")
                    continue
                binding = next(
                    (scope[arg] for scope in reversed(scopes) if arg in scope), None
                )
                if binding is None:
                    _fail(instruction, f"undefined variable {arg!r}")
                if op in {"ASSIGN", "ASSERT_MUTABLE"} and not binding[2]:
                    _fail(instruction, f"cannot assign to immutable variable {arg!r}")
                resolved[operation.offset] = binding
    # A malformed CFG with partially lowered lexical scopes is rejected;
    # approved main()->Unit programs are expected to close all scopes.
    if len(scopes) != 1:
        raise ValueError("Native Value IR has unbalanced lexical scopes")
    return resolved, variables

def _emit_c(value: ValueProgram) -> str:
    verify_value_ir(value)
    if len(value.functions) != 1 or value.functions[0].name != "main":
        origin = value.cfg.functions[0].token
        raise SamhusError("Native Value IR subset: only main() supported",
                          origin.line, origin.column)
    function = value.functions[0]
    signature = value.cfg.functions[0]
    if signature.params or signature.return_type != "Unit":
        raise SamhusError("Native Value IR subset: main must be fn main() -> Unit",
                          signature.token.line, signature.token.column)
    blocks = {block.label: block for block in function.blocks}
    types = {}
    for block in function.blocks:
        for phi in block.phis:
            types[phi.result] = phi.type_name
        for op in block.operations:
            if op.output is not None:
                types[op.output] = op.output_type

    resolved, variables = _collect_locals(function, types)
    valid = {"Int", "Bool", "Unit"}
    for block in function.blocks:
        for phi in block.phis:
            if phi.type_name not in {"Int", "Bool"}:
                raise SamhusError(
                    f"Native Value IR subset: unsupported PHI type {phi.type_name}",
                    signature.token.line, signature.token.column,
                )
        for op in block.operations:
            instr = op.instruction
            if op.output is not None and op.output_type not in valid:
                _fail(instr, f"unsupported value type {op.output_type!r}")
            if instr.op not in {
                "TICK", "PUSH", "POP", "UNARY", "BINARY", "CALL", "JUMP",
                "BRANCH_FALSE", "KEEP_FALSE", "KEEP_TRUE", "EXPECT_BOOL",
                "SCOPE_IN", "SCOPE_OUT", "RETURN_VOID",
                "LOAD", "DECLARE", "ASSIGN", "ASSERT_MUTABLE", "ASSERT_FRESH",
            }:
                _fail(instr, f"unsupported instruction {instr.op!r}")

    # Hoist all value registers, including PHI destinations, to function
    # scope so C's goto cannot jump into variable initialization.
    lines = [
        PRELUDE,
        "static uint64_t sh_native_steps = UINT64_C(0);",
        "static void sh_tick(void) {",
        '    if (++sh_native_steps > UINT64_C(100000)) sh_fail("Execution step limit exceeded (100000)");',
        "}",
        "static void sh_fn_main(void) {",
    ]
    for symbol in sorted(types):
        lines.append(f"    int64_t {_symbol(symbol)} = INT64_C(0);")
    for local_name in variables:
        lines.append(f"    int64_t {local_name} = INT64_C(0);")
    lines.append(f"    goto shb_{function.blocks[0].label};")
    for block in function.blocks:
        lines.append(f"shb_{block.label}: ;")
        for op in block.operations:
            inst = op.instruction
            op_name, arg = inst.op, inst.arg
            dst = _symbol(op.output) if op.output else None
            args = tuple(_symbol(item) for item in op.inputs)
            arg_types = tuple(types[item] for item in op.inputs)
            if op_name == "LOAD":
                local_name, kind, _mutable = resolved[op.offset]
                if op.output_type != kind:
                    _fail(inst, f"LOAD type mismatch for {arg!r}")
                lines.append(f"    {dst} = {local_name};")
            elif op_name == "DECLARE":
                local_name, kind, _mutable = resolved[op.offset]
                if arg_types != (kind,):
                    _fail(inst, f"DECLARE type mismatch for {arg[0]!r}")
                lines.append(f"    {local_name} = {args[0]};")
            elif op_name == "ASSIGN":
                local_name, kind, _mutable = resolved[op.offset]
                if arg_types != (kind,):
                    _fail(inst, f"ASSIGN type mismatch for {arg!r}")
                lines.append(f"    {local_name} = {args[0]};")
            elif op_name == "PUSH":
                if type(arg) is bool:
                    lines.append(f"    {dst} = INT64_C({1 if arg else 0});")
                elif type(arg) is int and 0 <= arg <= MAX_INT:
                    lines.append(f"    {dst} = INT64_C({arg});")
                else:
                    _fail(inst, "Int literals must be nonnegative signed 64-bit or Bool")
            elif op_name == "UNARY":
                if arg == "!" and arg_types == ("Bool",):
                    lines.append(f"    {dst} = !{args[0]};")
                elif arg == "-" and arg_types == ("Int",):
                    lines.append(f"    {dst} = sh_neg({args[0]});")
                else:
                    _fail(inst, f"unsupported unary {arg!r} on {arg_types}")
            elif op_name == "BINARY":
                if arg_types == ("Int", "Int"):
                    checked = {"+": "sh_add", "-": "sh_sub", "*": "sh_mul",
                               "/": "sh_div"}
                    if arg in checked:
                        lines.append(f"    {dst} = {checked[arg]}({args[0]}, {args[1]});")
                    elif arg in {"<", "<=", ">", ">=", "==", "!="}:
                        lines.append(f"    {dst} = ({args[0]} {arg} {args[1]});")
                    else:
                        _fail(inst, f"unsupported Int binary operator {arg!r}")
                elif arg_types == ("Bool", "Bool") and arg in {"==", "!="}:
                    lines.append(f"    {dst} = ({args[0]} {arg} {args[1]});")
                else:
                    _fail(inst, f"unsupported binary {arg!r} on {arg_types}")
            elif op_name == "CALL":
                function_name, count = arg
                if function_name == "println" and count == 1:
                    if arg_types == ("Int",):
                        lines.append(f'    printf("%" PRId64 "\\n", {args[0]});')
                    elif arg_types == ("Bool",):
                        lines.append(f'    puts({args[0]} ? "true" : "false");')
                    else:
                        _fail(inst, f"println does not support {arg_types}")
                elif function_name == "assert" and count == 1 and arg_types == ("Bool",):
                    lines.append(f'    if (!{args[0]}) sh_fail("Assertion failed");')
                else:
                    _fail(inst, f"unsupported call {function_name!r}")
                lines.append(f"    {dst} = INT64_C(0);")
            elif op_name == "EXPECT_BOOL":
                if arg_types != ("Bool",):
                    _fail(inst, "boolean operand required")
            elif op_name in {"BRANCH_FALSE", "KEEP_TRUE", "KEEP_FALSE"}:
                if arg_types != ("Bool",):
                    _fail(inst, f"{op_name} requires Bool")
                if op_name == "BRANCH_FALSE":
                    kind, target = arg
                    if kind not in {"if", "while"}:
                        _fail(inst, f"unsupported conditional branch kind {kind!r}")
                    condition = f"!{args[0]}"
                else:
                    target = arg
                    condition = args[0] if op_name == "KEEP_TRUE" else f"!{args[0]}"
                successor = next((label for label in block.successors if label != target),target)
                lines.append(f"    if ({condition}) {{")
                _emit_edge(lines, block.label, target, blocks)
                lines.append("    } else {")
                _emit_edge(lines, block.label, successor, blocks)
                lines.append("    }")
            elif op_name == "JUMP":
                _emit_edge(lines, block.label, arg, blocks)
            elif op_name == "RETURN_VOID":
                lines.append("    return;")
            elif op_name == "TICK":
                lines.append("    sh_tick();")
            elif op_name in {"POP", "SCOPE_IN", "SCOPE_OUT",
                             "ASSERT_FRESH", "ASSERT_MUTABLE"}:
                # Statically enforced in _collect_locals; TICK still tracks
                # each statement and each while iteration at runtime.
                pass
        last = block.operations[-1].instruction.op
        if last not in {"JUMP", "BRANCH_FALSE", "KEEP_TRUE", "KEEP_FALSE", "RETURN_VOID"}:
            if len(block.successors) != 1:
                raise ValueError("Invalid native Value IR fallthrough")
            _emit_edge(lines, block.label, block.successors[0], blocks)
    lines += ["}", "int main(void) {", "    sh_fn_main();", "    return 0;", "}", ""]
    return "\n".join(lines)


def emit_value_ir_c(program: Program) -> str:
    """Compile restricted checked Int/Bool variables/branches/loops to C11."""
    return _emit_c(compile_value_ir(program))
