"""Opt-in, semantics-preserving experimental optimization of CFG stack IR.

Only tiny, demonstrably pure literal expressions are folded. Runtime errors
and side effects are NEVER evaluated by the optimizer. This is not an SSA
optimizer, and the native C11 backend does not consume this optimized IR.
"""
from dataclasses import dataclass, replace
from decimal import Decimal

from .bytecode import Instruction
from .errors import SamhusError
from .ir import ProgramIR, verify_ir
from .numbers import arithmetic, negate
from .values import NullValue, structural_equal

MAX_FOLD_INT_BITS = 4096
MAX_FOLD_STRING_CHARS = 4096

@dataclass(frozen=True)
class OptimizationStats:
    folded_binary: int = 0
    folded_unary: int = 0
    discarded_literals: int = 0

    @property
    def total(self) -> int:
        return self.folded_binary + self.folded_unary + self.discarded_literals


def _plain(value) -> bool:
    return type(value) in (int, float, str, bool, NullValue)


def _bounded(value) -> bool:
    if type(value) is int:
        return value.bit_length() <= MAX_FOLD_INT_BITS
    if type(value) is str:
        return len(value) <= MAX_FOLD_STRING_CHARS
    return _plain(value)


def _fold_unary(op: str, right, token):
    if op == "!":
        if type(right) is not bool:
            return None
        return not right
    if op == "-" and type(right) in (int, float):
        return negate(right, token)
    return None


def _fold_binary(op: str, left, right, token):
    if op in {"==", "!="}:
        equal = structural_equal(left, right)
        return equal if op == "==" else not equal
    if op not in {"+", "-", "*", "/", "<", "<=", ">", ">="}:
        return None
    # String concatenation is bounded, and neither branch calls user code.
    if op == "+" and type(left) is str and type(right) is str:
        if len(left) + len(right) <= MAX_FOLD_STRING_CHARS:
            return left + right
        return None
    if type(left) not in (int, float) or type(right) not in (int, float):
        return None
    return arithmetic(op, left, right, token)


def _optimize_block(code: tuple[Instruction, ...]) -> tuple[tuple[Instruction, ...], OptimizationStats]:
    sequence = list(code)
    binary = unary = discarded = 0
    changed = True
    # Repeated folding handles nested constant expressions while keeping
    # source-token order and statement TICK instructions intact.
    while changed:
        changed = False
        out = []
        i = 0
        while i < len(sequence):
            if (i + 2 < len(sequence)
                    and sequence[i].op == sequence[i+1].op == "PUSH"
                    and sequence[i+2].op == "BINARY"):
                left, right, action = sequence[i:i+3]
                if _plain(left.arg) and _plain(right.arg):
                    try:
                        value = _fold_binary(action.arg, left.arg, right.arg, action.token)
                    except (SamhusError, ArithmeticError, OverflowError, ValueError):
                        value = None
                    if value is not None and _bounded(value):
                        out.append(Instruction("PUSH", value, action.token))
                        binary += 1
                        i += 3
                        changed = True
                        continue
            if (i + 1 < len(sequence) and sequence[i].op == "PUSH"
                    and sequence[i+1].op == "UNARY"):
                previous, action = sequence[i:i+2]
                if _plain(previous.arg):
                    try:
                        value = _fold_unary(action.arg, previous.arg, action.token)
                    except (SamhusError, ArithmeticError, OverflowError, ValueError):
                        value = None
                    if value is not None and _bounded(value):
                        out.append(Instruction("PUSH", value, action.token))
                        unary += 1
                        i += 2
                        changed = True
                        continue
            if i + 1 < len(sequence) and sequence[i].op == "PUSH" and sequence[i+1].op == "POP":
                if _plain(sequence[i].arg):
                    discarded += 1
                    i += 2
                    changed = True
                    continue
            out.append(sequence[i])
            i += 1
        sequence = out
    return tuple(sequence), OptimizationStats(binary, unary, discarded)


def optimize_ir(ir: ProgramIR) -> tuple[ProgramIR, OptimizationStats]:
    """Fold pure literals within blocks, retain all failures at runtime.

    The exact same CFG verifier checks both input and output.
    """
    verify_ir(ir)
    functions = []
    binary = unary = discarded = 0
    for function in ir.functions:
        blocks = []
        for block in function.blocks:
            optimized, stats = _optimize_block(block.instructions)
            if not optimized:
                # Removing the only instructions would make an invalid basic
                # block. Keep the original rather than changing semantics.
                optimized = block.instructions
                stats = OptimizationStats()
            blocks.append(replace(block, instructions=optimized))
            binary += stats.folded_binary
            unary += stats.folded_unary
            discarded += stats.discarded_literals
        functions.append(replace(function, blocks=tuple(blocks)))
    result = replace(ir, functions=tuple(functions))
    verify_ir(result)
    return result, OptimizationStats(binary, unary, discarded)
