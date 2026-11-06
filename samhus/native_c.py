"""EXPERIMENTAL restricted native-C lowering for explicitly typed Samhus.

Only a documented subset of the existing language is accepted. This
prototype outputs C11 source, which a system C compiler can turn into a
standalone executable. The *compiler itself* still runs on Python.

CRITICAL SEMANTIC LIMIT: the general Samhus Int is arbitrary-precision;
this native experiment uses CHECKED SIGNED 64-BIT integers and rejects
overflow. Therefore it cannot claim full Samhus language equivalence.
"""
from dataclasses import dataclass

from .errors import SamhusError
from .parser import Expr, Function, Program, Stmt, parse_program
from .typecheck import TypeChecker


TYPES = {"Int": "int64_t", "Bool": "bool", "String": "const char *", "Unit": "void"}
MAX_INT = 2**63 - 1
MIN_INT = -(2**63)


def _fail(node: Expr | Stmt | Function, message: str) -> None:
    raise SamhusError("Native subset: " + message, node.token.line, node.token.column)


@dataclass
class _Result:
    steps: list[str]
    value: str
    kind: str


class _Emitter:
    def __init__(self, program: Program):
        self.functions = {fn.name: fn for fn in program.functions}
        self.counter = 0
        self.env: list[dict[str, tuple[str, bool]]] = []

    def temp(self) -> str:
        self.counter += 1
        return f"sh_tmp_{self.counter}"

    def lookup(self, name: str, node: Expr | Stmt) -> tuple[str, bool]:
        for scope in reversed(self.env):
            if name in scope:
                return scope[name]
        _fail(node, f"undefined variable {name!r}")
        raise AssertionError("unreachable")

    def store(self, result: _Result) -> tuple[list[str], str]:
        steps = list(result.steps)
        if result.kind == "Unit":
            steps.append(f"{result.value};")
            return steps, ""
        variable = self.temp()
        steps.append(f"{TYPES[result.kind]} {variable} = {result.value};")
        return steps, variable

    def expression(self, node: Expr) -> _Result:
        if node.kind == "literal":
            if type(node.value) is bool:
                return _Result([], "true" if node.value else "false", "Bool")
            if type(node.value) is int:
                if not 0 <= node.value <= MAX_INT:
                    _fail(node, "integer literal exceeds signed 64-bit range")
                return _Result([], f"INT64_C({node.value})", "Int")
            if type(node.value) is str:
                if "\x00" in node.value:
                    _fail(node, "NUL bytes in strings are not supported")
                raw = node.value.encode("utf-8")
                # Fixed-width octal escapes avoid accidental C hex escape merging.
                text = '"' + "".join(f"\\{b:03o}" for b in raw) + '"'
                return _Result([], text, "String")
            _fail(node, "unsupported literal")
        if node.kind == "name":
            kind, _mutable = self.lookup(node.value, node)
            return _Result([], "sh_" + node.value, kind)
        if node.kind == "unary":
            if (node.value == "-" and node.right.kind == "literal"
                    and type(node.right.value) is int and node.right.value == 2**63):
                return _Result([], "INT64_MIN", "Int")
            right = self.expression(node.right)
            if node.value == "!" and right.kind != "Bool":
                _fail(node, "'!' expects Bool")
            if node.value == "-" and right.kind != "Int":
                _fail(node, "unary '-' expects Int")
            statements, value = self.store(right)
            operation = f"(!{value})" if node.value == "!" else f"sh_neg({value})"
            return _Result(statements, operation, "Bool" if node.value == "!" else "Int")
        if node.kind == "binary":
            left = self.expression(node.left)
            if node.value in {"&&", "||"}:
                if left.kind != "Bool":
                    _fail(node, "boolean expression expects Bool")
                steps, left_name = self.store(left)
                result_name = self.temp()
                steps.append(f"bool {result_name} = {left_name};")
                right = self.expression(node.right)
                if right.kind != "Bool":
                    _fail(node, "boolean expression expects Bool")
                steps.append(f"if ({result_name}) {{" if node.value == "&&" else f"if (!{result_name}) {{")
                inside, right_name = self.store(right)
                steps.extend("    " + line for line in inside)
                steps.append(f"    {result_name} = {right_name};")
                steps.append("}")
                return _Result(steps, result_name, "Bool")
            left_steps, left_name = self.store(left)
            right = self.expression(node.right)
            right_steps, right_name = self.store(right)
            steps = left_steps + right_steps
            op = node.value
            if op in {"+", "-", "*", "/", "<", "<=", ">", ">="}:
                if left.kind != "Int" or right.kind != "Int":
                    _fail(node, f"native '{op}' is restricted to Int operands")
                if op in {"+", "-", "*", "/"}:
                    fname = {"+": "sh_add", "-": "sh_sub", "*": "sh_mul", "/": "sh_div"}[op]
                    return _Result(steps, f"{fname}({left_name}, {right_name})", "Int")
                return _Result(steps, f"({left_name} {op} {right_name})", "Bool")
            if op in {"==", "!="}:
                if left.kind != right.kind:
                    return _Result(steps, "false" if op == "==" else "true", "Bool")
                if left.kind == "String":
                    return _Result(steps, f"(strcmp({left_name}, {right_name}) {op} 0)", "Bool")
                if left.kind == "Unit":
                    _fail(node, "Unit comparisons are not implemented")
                return _Result(steps, f"({left_name} {op} {right_name})", "Bool")
            _fail(node, f"unsupported operator {op!r}")
        if node.kind == "call":
            fn = self.functions.get(node.value)
            if fn is None:
                _fail(node, f"builtin or unknown function {node.value!r} is unsupported in expressions")
            if len(node.args) != len(fn.params):
                _fail(node, f"{node.value} expects {len(fn.params)} arguments")
            steps = []
            arguments = []
            for expr, expected in zip(node.args, fn.param_types):
                value = self.expression(expr)
                if value.kind != expected:
                    _fail(expr, f"expected {expected}, got {value.kind}")
                instructions, argument = self.store(value)
                steps.extend(instructions)
                arguments.append(argument)
            return _Result(steps, f"sh_{fn.name}({', '.join(arguments)})", fn.return_type)
        _fail(node, f"unsupported expression {node.kind!r}")
        raise AssertionError("unreachable")

    def statement(self, stmt: Stmt, depth: int) -> list[str]:
        prefix = "    " * depth

        def lines(items: list[str]) -> list[str]:
            return [prefix + item for item in items]

        if stmt.kind == "declare":
            scope = self.env[-1]
            if stmt.name in scope:
                _fail(stmt, f"duplicate declaration {stmt.name}")
            kind = stmt.declared_type
            if kind not in ("Int", "Bool", "String"):
                _fail(stmt, "native declarations require explicit Int, Bool or String")
            # Mark before checking the RHS, like the tree interpreter's
            # duplicate declaration check; only type-correct programs compile.
            value = self.expression(stmt.expr)
            if value.kind != kind:
                _fail(stmt, f"expected {kind}, got {value.kind}")
            result = lines(value.steps)
            result.append(prefix + f"{TYPES[kind]} sh_{stmt.name} = {value.value};")
            scope[stmt.name] = (kind, stmt.mutable)
            return result
        if stmt.kind == "assign":
            kind, mutable = self.lookup(stmt.name, stmt)
            if not mutable:
                _fail(stmt, f"cannot assign to immutable variable {stmt.name}")
            value = self.expression(stmt.expr)
            if value.kind != kind:
                _fail(stmt, f"expected {kind}, got {value.kind}")
            return lines(value.steps + [f"sh_{stmt.name} = {value.value};"])
        if stmt.kind == "expr":
            call = stmt.expr
            if call.kind == "call" and call.value in {"println", "assert"}:
                if len(call.args) != 1:
                    _fail(stmt, f"{call.value} requires exactly one argument")
                value = self.expression(call.args[0])
                statements, var = self.store(value)
                if call.value == "assert":
                    if value.kind != "Bool":
                        _fail(stmt, "assert requires Bool")
                    statements.append(f"if (!{var}) sh_fail(\"Assertion failed\");")
                elif value.kind == "String":
                    statements.append(f"puts({var});")
                elif value.kind == "Bool":
                    statements.append(f"puts({var} ? \"true\" : \"false\");")
                elif value.kind == "Int":
                    statements.append(f"printf(\"%\" PRId64 \"\\n\", {var});")
                else:
                    _fail(stmt, "native println accepts Int, Bool or String")
                return lines(statements)
            result = self.expression(call)
            return lines(result.steps + [result.value + ";"])
        if stmt.kind == "return":
            if self.current_return == "Unit":
                _fail(stmt, "return expressions in Unit functions are not supported")
            result = self.expression(stmt.expr)
            if result.kind != self.current_return:
                _fail(stmt, f"expected return {self.current_return}, got {result.kind}")
            return lines(result.steps + [f"return {result.value};"])
        if stmt.kind == "if":
            cond = self.expression(stmt.expr)
            if cond.kind != "Bool":
                _fail(stmt, "if condition requires Bool")
            result = lines(cond.steps + [f"if ({cond.value}) {{"])
            result.extend(self.block(stmt.then_body, depth + 1))
            result.append(prefix + "}")
            if stmt.else_body:
                result[-1] += " else {"
                result.extend(self.block(stmt.else_body, depth + 1))
                result.append(prefix + "}")
            return result
        if stmt.kind == "while":
            cond = self.expression(stmt.expr)
            if cond.kind != "Bool":
                _fail(stmt, "while condition requires Bool")
            result = [prefix + "while (true) {"]
            result.extend("    " + line for line in lines(cond.steps))
            result.append(prefix + f"    if (!({cond.value})) break;")
            result.extend(self.block(stmt.then_body, depth + 1))
            result.append(prefix + "}")
            return result
        _fail(stmt, f"unsupported statement {stmt.kind!r}")
        raise AssertionError("unreachable")

    def block(self, body: tuple[Stmt, ...], depth: int) -> list[str]:
        self.env.append({})
        try:
            result = []
            for statement in body:
                result.extend(self.statement(statement, depth))
            return result
        finally:
            self.env.pop()

    def function(self, fn: Function) -> list[str]:
        self.current_return = fn.return_type
        scope = {name: (kind, False) for name, kind in zip(fn.params, fn.param_types)}
        self.env = [scope]
        result = [self.signature(fn) + " {"]
        for statement in fn.body:
            result.extend(self.statement(statement, 1))
        if fn.return_type == "Unit":
            result.append("    return;")
        result.extend(["}", ""])
        return result

    @staticmethod
    def signature(fn: Function) -> str:
        ret = TYPES[fn.return_type]
        args = ", ".join(f"{TYPES[kind]} sh_{name}" for name, kind in zip(fn.params, fn.param_types))
        return f"static {ret} sh_{fn.name}({args or 'void'})"


PRELUDE = r'''/* Generated by experimental Samhus C backend; do not hand-edit.
 * This C99/C11 target has checked Int64, NOT Samhus arbitrary precision Int.
 * Compiler produces machine code via an external C compiler; no Python runtime.
 */
#include <stdbool.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

static void sh_fail(const char *message) {
    fprintf(stderr, "Samhus native runtime error: %s\n", message);
    exit(2);
}
static int64_t sh_add(int64_t a, int64_t b) {
    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b))
        sh_fail("integer overflow");
    return a + b;
}
static int64_t sh_sub(int64_t a, int64_t b) {
    if ((b < 0 && a > INT64_MAX + b) || (b > 0 && a < INT64_MIN + b))
        sh_fail("integer overflow");
    return a - b;
}
static uint64_t sh_magnitude(int64_t value) {
    return value < 0 ? (uint64_t)(-(value + 1)) + UINT64_C(1) : (uint64_t)value;
}
static int64_t sh_mul(int64_t a, int64_t b) {
    bool negative = (a < 0) != (b < 0);
    uint64_t left = sh_magnitude(a), right = sh_magnitude(b);
    uint64_t max = negative ? (uint64_t)INT64_MAX + UINT64_C(1) : (uint64_t)INT64_MAX;
    if (right && left > max / right) sh_fail("integer overflow");
    uint64_t product = left * right;
    if (negative && product == (uint64_t)INT64_MAX + UINT64_C(1)) return INT64_MIN;
    return negative ? -(int64_t)product : (int64_t)product;
}
static int64_t sh_neg(int64_t value) {
    if (value == INT64_MIN) sh_fail("integer overflow");
    return -value;
}
static int64_t sh_div(int64_t a, int64_t b) {
    if (b == 0) sh_fail("Division by zero");
    if (a == INT64_MIN && b == -1) sh_fail("integer overflow");
    return a / b;
}
'''


def emit_c(source: str) -> str:
    """Translate a strictly typed, intentionally restricted Samhus subset."""
    program = parse_program(source)
    # Existing semantic checker catches a variety of source errors early.
    TypeChecker(program).check()
    emitter = _Emitter(program)
    for fn in program.functions:
        if fn.return_type not in TYPES:
            _fail(fn, "every native function needs an explicit return type")
        if any(kind not in ("Int", "String", "Bool") for kind in fn.param_types):
            _fail(fn, "every native parameter needs Int, String or Bool annotation")
    main = next(fn for fn in program.functions if fn.name == "main")
    if main.return_type != "Unit":
        _fail(main, "native main must explicitly return Unit")
    lines = [PRELUDE, "/* Function forward declarations */"]
    lines.extend(_Emitter.signature(fn) + ";" for fn in program.functions)
    lines.append("")
    for fn in program.functions:
        lines.extend(emitter.function(fn))
    lines.extend(["int main(void) {", "    sh_main();", "    return 0;", "}", ""])
    return "\n".join(lines)
