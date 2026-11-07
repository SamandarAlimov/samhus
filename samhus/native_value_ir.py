"""Experimental Value IR -> C11 backend for checked Int64/Bool and Strings.

Strings are immutable length-tracked views of static UTF-8 literals or an
opt-in bounded process-lifetime concatenation arena. Neither the arena nor
the native subset represents a finalized ownership or memory safety model.
"""
from .errors import SamhusError
from .native_c import MAX_INT, PRELUDE
from .parser import Program


MAX_NATIVE_LITERAL_BYTES = 65536


def _ctype(kind: str) -> str:
    return "sh_string" if kind == "String" else "int64_t"


def _zero(kind: str) -> str:
    return "(sh_string){NULL, 0}" if kind == "String" else "INT64_C(0)"


def _static_utf8_literal(value: str, instruction) -> str:
    """Octal escape every byte: safe against quote, backslash, and hex merging."""
    if "\x00" in value:
        _fail(instruction, "NUL byte in native String literal is unsupported")
    try:
        data = value.encode("utf-8", errors="strict")
    except UnicodeError:
        _fail(instruction, "native String literal must be valid UTF-8")
    if len(data) > MAX_NATIVE_LITERAL_BYTES:
        _fail(instruction, f"native String literal exceeds {MAX_NATIVE_LITERAL_BYTES} UTF-8 bytes")
    return "\"" + "".join(f"\\{byte:03o}" for byte in data) + "\""
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


def _emit_edge(lines: list[str], predecessor: str, target: str, blocks, types) -> None:
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
    for index, (destination, source) in enumerate(incoming):
        if types[source] != types[destination]:
            raise ValueError("Native Value IR PHI requires matching source/target types")
        lines.append(f"        {_ctype(types[destination])} sh_move_{index} = {_symbol(source)};")
    for index, (destination, _) in enumerate(incoming):
        lines.append(f"        {_symbol(destination)} = sh_move_{index};")
    lines.append(f"        goto shb_{target};")
    lines.append("    }")



def _collect_locals(function, types, signature):
    """Resolve lexical bindings per CFG edge, not textual block order.

    Branches that return early do not necessarily emit reachable SCOPE_OUT
    instructions. CFG forward analysis handles those exits and checks that
    all other control-flow joins agree on their live lexical bindings.
    """
    blocks = {block.label: block for block in function.blocks}
    parameters = {
        name: (f"sh_arg_{i}", kind, False)
        for i, (name, kind) in enumerate(zip(signature.params, signature.param_types))
    }
    pending = [function.blocks[0].label]
    in_state = {pending[0]: (parameters,)}
    resolved = {}
    declared = set()
    while pending:
        name = pending.pop()
        scopes = [dict(scope) for scope in in_state[name]]
        for operation in blocks[name].operations:
            instruction = operation.instruction
            op, arg = instruction.op, instruction.arg
            if op == "SCOPE_IN":
                scopes.append({})
            elif op == "SCOPE_OUT":
                if len(scopes) == 1:
                    _fail(instruction, "scope underflow")
                scopes.pop()
            elif op in {"DECLARE", "LOAD", "ASSIGN", "ASSERT_MUTABLE", "ASSERT_FRESH"}:
                if op == "DECLARE":
                    variable_name, mutable, annotation = arg
                    if variable_name in scopes[-1]:
                        _fail(instruction, f"duplicate declaration {variable_name!r}")
                    kind = annotation or types[operation.inputs[0]]
                    if kind not in {"Int", "Bool", "String"}:
                        _fail(instruction, f"unsupported declared type {kind!r}")
                    cell = (f"sh_local_{operation.offset}", kind, mutable)
                    scopes[-1][variable_name] = cell
                    declared.add(cell[0])
                    binding = cell
                elif op == "ASSERT_FRESH":
                    if arg in scopes[-1]:
                        _fail(instruction, f"duplicate declaration {arg!r}")
                    continue
                else:
                    binding = next(
                        (scope[arg] for scope in reversed(scopes) if arg in scope),
                        None,
                    )
                    if binding is None:
                        _fail(instruction, f"undefined variable {arg!r}")
                    if op in {"ASSIGN", "ASSERT_MUTABLE"} and not binding[2]:
                        _fail(instruction, f"cannot assign to immutable variable {arg!r}")
                previous = resolved.get(operation.offset)
                if previous is not None and previous != binding:
                    _fail(instruction, "incompatible lexical binding across CFG paths")
                resolved[operation.offset] = binding
        successor_state = tuple(scopes)
        for label in blocks[name].successors:
            previous = in_state.get(label)
            if previous is None:
                in_state[label] = successor_state
                pending.append(label)
            elif previous != successor_state:
                raise SamhusError(
                    "Native Value IR subset: conflicting lexical scopes at control-flow join",
                    signature.token.line, signature.token.column,
                )
    return resolved, sorted(declared)


def _emit_one(function, signature, functions) -> list[str]:
    """Translate a verified Value IR function; all temps are call-local."""
    blocks = {block.label: block for block in function.blocks}
    types = {}
    for block in function.blocks:
        for phi in block.phis:
            types[phi.result] = phi.type_name
        for op in block.operations:
            if op.output is not None:
                types[op.output] = op.output_type

    resolved, variables = _collect_locals(function, types, signature)
    valid = {"Int", "Bool", "Unit", "String"}
    for block in function.blocks:
        for phi in block.phis:
            if phi.type_name not in {"Int", "Bool", "String"}:
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
                "RETURN", "INDEX",
            }:
                _fail(instr, f"unsupported instruction {instr.op!r}")

    # C locals per invocation prevent recursive frames sharing value cells.
    result_type = signature.return_type
    result_c = "void" if result_type == "Unit" else _ctype(result_type)
    parameters = ", ".join(f"{_ctype(kind)} sh_arg_{i}" for i, kind in enumerate(signature.param_types)) or "void"
    lines = [
        f"static {result_c} {functions[signature.name][0]}({parameters}) {{",
        "    sh_enter();",
        "    sh_tick();",
    ]
    for symbol in sorted(types):
        lines.append(f"    {_ctype(types[symbol])} {_symbol(symbol)} = {_zero(types[symbol])};")
    for local_name in variables:
        # Each declaration offset has a single well-typed C cell.
        declaration = next(
            binding for binding in resolved.values() if binding[0] == local_name
        )
        lines.append(f"    {_ctype(declaration[1])} {local_name} = {_zero(declaration[1])};")
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
                if type(arg) is str:
                    literal = _static_utf8_literal(arg, inst)
                    lines.append(
                        f"    {dst} = (sh_string){{(const unsigned char *){literal}, "
                        f"sizeof({literal}) - 1}};"
                    )
                elif type(arg) is bool:
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
                elif arg_types == ("String", "String") and arg == "+":
                    if op.output_type != "String":
                        _fail(inst, "native String concat requires String result")
                    lines.append(f"    {dst} = sh_concat({args[0]}, {args[1]});")
                elif arg_types == ("String", "String") and arg in {"==", "!="}:
                    comparator = "sh_string_equal"
                    comparison = f"{comparator}({args[0]}, {args[1]})"
                    lines.append(f"    {dst} = {comparison if arg == '==' else '!' + comparison};")
                else:
                    _fail(inst, f"unsupported binary {arg!r} on {arg_types}")
            elif op_name == "INDEX":
                if arg_types != ("String", "Int") or op.output_type != "String":
                    _fail(inst, f"native INDEX supports String[Int], got {arg_types}")
                lines.append(f"    {dst} = sh_utf8_index({args[0]}, {args[1]});")
            elif op_name == "CALL":
                function_name, count = arg
                # VM counts built-in invocations as execution steps. User
                # calls tick in sh_enter() at the callee's entry instead.
                if function_name in {"println", "assert", "len"}:
                    lines.append("    sh_tick();")
                if function_name == "println" and count == 1:
                    if arg_types == ("Int",):
                        lines.append(f'    printf("%" PRId64 "\\n", {args[0]});')
                    elif arg_types == ("Bool",):
                        lines.append(f'    puts({args[0]} ? "true" : "false");')
                    elif arg_types == ("String",):
                        lines.append(f"    sh_print_string({args[0]});")
                    else:
                        _fail(inst, f"println does not support {arg_types}")
                elif function_name == "assert" and count == 1 and arg_types == ("Bool",):
                    lines.append(f'    if (!{args[0]}) sh_fail("Assertion failed");')
                elif function_name == "len" and count == 1 and arg_types == ("String",):
                    lines.append(f"    {dst} = sh_utf8_len({args[0]});")
                    continue
                elif function_name in functions:
                    target, target_sig = functions[function_name]
                    expected = target_sig.param_types
                    if count != len(expected) or arg_types != expected:
                        _fail(inst, f"invalid native call to {function_name!r}: "
                                    f"expected {expected}, got {arg_types}")
                    argument_list = ", ".join(args)
                    if target_sig.return_type == "Unit":
                        if op.output_type != "Unit":
                            _fail(inst, f"bad Unit result type from {function_name!r}")
                        lines.append(f"    {target}({argument_list});")
                        lines.append(f"    {dst} = {_zero(op.output_type)};")
                    elif op.output_type == target_sig.return_type:
                        lines.append(f"    {dst} = {target}({argument_list});")
                    else:
                        _fail(inst, f"bad native return type from {function_name!r}")
                    continue
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
                _emit_edge(lines, block.label, target, blocks, types)
                lines.append("    } else {")
                _emit_edge(lines, block.label, successor, blocks, types)
                lines.append("    }")
            elif op_name == "JUMP":
                _emit_edge(lines, block.label, arg, blocks, types)
            elif op_name == "RETURN":
                if arg_types != (result_type,):
                    _fail(inst, f"return mismatch: expected {result_type}, got {arg_types}")
                lines.append("    sh_leave();")
                lines.append("    return;" if result_type == "Unit" else f"    return {args[0]};")
            elif op_name == "RETURN_VOID":
                if result_type == "Unit":
                    lines.append("    sh_leave();")
                    lines.append("    return;")
                else:
                    lines.append('    sh_fail("Non-Unit function exited without return");')
            elif op_name == "TICK":
                lines.append("    sh_tick();")
            elif op_name in {"POP", "SCOPE_IN", "SCOPE_OUT",
                             "ASSERT_FRESH", "ASSERT_MUTABLE"}:
                # Statically enforced in _collect_locals; TICK still tracks
                # each statement and each while iteration at runtime.
                pass
        last = block.operations[-1].instruction.op
        if last not in {"JUMP", "BRANCH_FALSE", "KEEP_TRUE", "KEEP_FALSE", "RETURN", "RETURN_VOID"}:
            if len(block.successors) != 1:
                raise ValueError("Invalid native Value IR fallthrough")
            _emit_edge(lines, block.label, block.successors[0], blocks, types)
    lines.append("}")
    return lines


def _emit_c(value: ValueProgram) -> str:
    verify_value_ir(value)
    signatures = {fn.name: fn for fn in value.cfg.functions}
    main = signatures.get("main")
    if main is None or main.params or main.return_type != "Unit":
        token = main.token if main is not None else value.cfg.functions[0].token
        raise SamhusError("Native Value IR subset: main must be fn main() -> Unit",
                          token.line, token.column)
    functions = {}
    for idx, fn in enumerate(value.cfg.functions):
        if (fn.return_type not in {"Int", "Bool", "String", "Unit"}
                or len(fn.params) != len(fn.param_types)
                or any(kind not in {"Int", "Bool", "String"} for kind in fn.param_types)):
            raise SamhusError(
                "Native Value IR subset: functions require explicit Int/Bool/String parameters and Int/Bool/String/Unit return",
                fn.token.line, fn.token.column,
            )
        functions[fn.name] = ("sh_fn_main" if fn.name == "main" else f"sh_fn_{idx}", fn)
    lines = [
        PRELUDE,
        "static uint64_t sh_native_steps = UINT64_C(0);",
        "static volatile uint64_t sh_native_calls = UINT64_C(0);",
        "static void sh_tick(void) {",
        '    if (++sh_native_steps > UINT64_C(100000)) sh_fail("Execution step limit exceeded (100000)");',
        "}",
        "static void sh_enter(void) {",
        '    if (++sh_native_calls > UINT64_C(128)) sh_fail("Function call depth limit exceeded (128)");',
        "}",
        "static void sh_leave(void) { --sh_native_calls; }",
    ]
    lines += [
        "typedef struct { const unsigned char *data; size_t size; } sh_string;",
    ]
    # Only binaries using String + String reserve arena storage.
    # Returned views outlive function frames; allocation is cumulative
    # and checked. This is not a permanent language memory model.
    needs_concat = any(
        op.instruction.op == "BINARY"
        and op.instruction.arg == "+"
        and op.output_type == "String"
        for fn in value.functions
        for block in fn.blocks
        for op in block.operations
    )
    if needs_concat:
        lines += [
            "#define SH_STRING_ARENA_LIMIT ((size_t)8388608)",
            "static unsigned char sh_string_arena[SH_STRING_ARENA_LIMIT];",
            "static size_t sh_string_arena_used = 0;",
            "static sh_string sh_concat(sh_string left, sh_string right) {",
            "    if (!left.size) return right;",
            "    if (!right.size) return left;",
            "    size_t remaining = SH_STRING_ARENA_LIMIT - sh_string_arena_used;",
            "    if (left.size > remaining || right.size > remaining - left.size)",
            '        sh_fail("String arena budget exceeded (8388608 bytes)");',
            "    size_t combined = left.size + right.size;",
            "    unsigned char *out = sh_string_arena + sh_string_arena_used;",
            "    memcpy(out, left.data, left.size);",
            "    memcpy(out + left.size, right.data, right.size);",
            "    sh_string_arena_used += combined;",
            "    return (sh_string){out, combined};",
            "}",
        ]
    lines += [
        "static size_t sh_cp_size(unsigned char leading) {",
        "    if (leading < 0x80u) return 1;",
        "    if (leading >= 0xc2u && leading <= 0xdfu) return 2;",
        "    if (leading >= 0xe0u && leading <= 0xefu) return 3;",
        "    if (leading >= 0xf0u && leading <= 0xf4u) return 4;",
        "    sh_fail(\"Invalid UTF-8 byte sequence\");",
        "    return 0;",
        "}",
        "static int64_t sh_utf8_len(sh_string value) {",
        "    int64_t size = INT64_C(0);",
        "    for (size_t i = 0; i < value.size;) {",
        "        size_t step = sh_cp_size(value.data[i]);",
        "        if (step > value.size - i) sh_fail(\"Truncated UTF-8\");",
        "        i += step;",
        "        ++size;",
        "    }",
        "    return size;",
        "}",
        "static sh_string sh_utf8_index(sh_string value, int64_t index) {",
        "    if (index < 0) sh_fail(\"Index out of bounds\");",
        "    int64_t position = INT64_C(0);",
        "    for (size_t i = 0; i < value.size;) {",
        "        size_t step = sh_cp_size(value.data[i]);",
        "        if (step > value.size - i) sh_fail(\"Truncated UTF-8\");",
        "        if (position == index) return (sh_string){value.data+i,step};",
        "        i += step;",
        "        ++position;",
        "    }",
        "    sh_fail(\"Index out of bounds\");",
        "    return (sh_string){NULL,0};",
        "}",
        "static int sh_string_equal(sh_string left, sh_string right) {",
        "    return left.size == right.size &&",
        "        (!left.size || memcmp(left.data, right.data, left.size) == 0);",
        "}",
        "static void sh_print_string(sh_string value) {",
        "    if (value.size) fwrite(value.data, 1, value.size, stdout);",
        "    putchar(10);",
        "}",
    ]
    # Forward prototypes permit recursive and out-of-order user calls.
    for fn in value.cfg.functions:
        return_c = "void" if fn.return_type == "Unit" else _ctype(fn.return_type)
        params_c = ", ".join(_ctype(kind) for kind in fn.param_types) or "void"
        lines.append(f"static {return_c} {functions[fn.name][0]}({params_c});")
    for fn in value.functions:
        lines.extend(_emit_one(fn, signatures[fn.name], functions))
    lines += ["int main(void) {", "    sh_fn_main();", "    return 0;", "}", ""]
    return "\n".join(lines)


def emit_value_ir_c(program: Program) -> str:
    """Compile restricted Int64/Bool/length-tracked String programs to C11."""
    return _emit_c(compile_value_ir(program))
