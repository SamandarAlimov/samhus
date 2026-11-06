"""Bytecode control-flow verifier tests using compiler output and invalid streams."""
import unittest

from samhus.bytecode import Bytecode, Code, Instruction, compile_source
from samhus.lexer import Token
from samhus.verify import BytecodeValidationError, verify_bytecode


TOKEN = Token("TEST", "", 1, 1)


def program(*commands):
    return Bytecode((Code("main", (), (), None, TOKEN, tuple(commands)),))


def ins(op, arg=None):
    return Instruction(op, arg, TOKEN)


class BytecodeVerifierTests(unittest.TestCase):
    def test_compiler_output_verifies(self):
        cases = [
            "fn main() {}",
            "fn main() { println(42) }",
            "fn main() { if true {} else {} }",
            "fn main() { var i=0; while i<2 { i=i+1 } }",
            "fn f(a: Int) -> Int { return a*2 }\nfn main() { println(f(21)) }",
            "fn main() { println(false && true); println(true || false) }",
            "fn main() { if true { if false {println(1)} else {println(2)} } }",
            "fn main() { return 1 }",
        ]
        for source in cases:
            with self.subTest(source=source):
                self.assertIsNotNone(compile_source(source))

    def test_unknown_opcode_rejected(self):
        with self.assertRaisesRegex(BytecodeValidationError, "unknown opcode"):
            verify_bytecode(program(ins("WHOOPS")))

    def test_stack_underflow_rejected(self):
        with self.assertRaisesRegex(BytecodeValidationError, "stack underflow"):
            verify_bytecode(program(ins("POP"), ins("RETURN_VOID")))

    def test_invalid_branch_rejected(self):
        with self.assertRaisesRegex(BytecodeValidationError, "invalid branch target"):
            verify_bytecode(program(ins("JUMP", 999), ins("RETURN_VOID")))

    def test_negative_scope_rejected(self):
        with self.assertRaisesRegex(BytecodeValidationError, "scope underflow"):
            verify_bytecode(program(ins("SCOPE_OUT"), ins("RETURN_VOID")))

    def test_missing_return_rejected(self):
        with self.assertRaisesRegex(BytecodeValidationError, "invalid branch target"):
            verify_bytecode(program(ins("TICK")))

    def test_nonempty_return_rejected(self):
        with self.assertRaisesRegex(BytecodeValidationError, "nonempty stack"):
            verify_bytecode(program(ins("PUSH", 1), ins("RETURN_VOID")))

    def test_malformed_call_rejected(self):
        with self.assertRaisesRegex(BytecodeValidationError, "malformed CALL"):
            verify_bytecode(program(ins("CALL", ("f", -1)), ins("RETURN_VOID")))

    def test_conflicting_merge_rejected(self):
        code = program(ins("PUSH", True), ins("BRANCH_FALSE", ("if", 4)),
                       ins("PUSH", 5), ins("JUMP", 4), ins("RETURN_VOID"))
        with self.assertRaisesRegex(BytecodeValidationError, "conflicting stack/scope"):
            verify_bytecode(code)

    def test_boolean_short_circuit_stack(self):
        compile_source('fn main() { println(false && true); println(true || false) }')


if __name__ == "__main__":
    unittest.main()
