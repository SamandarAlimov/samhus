"""Run with: python -m samhus run examples/hello.sahu"""
import argparse
from pathlib import Path
import sys

from . import __version__, SamhusError
from .typecheck import TypeChecker
from .astdump import dump_program
from .formatter import format_program, contains_comments
from .bytecode import compile_ast
from .ir import compile_ir, lower_ir
from .vm import VirtualMachine
from .runtime import Interpreter
from .native_c import emit_program_c
from .modules import load_program
import shutil
import subprocess
import tempfile


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="samhus", description="Samhus experimental interpreter")
    parser.add_argument("--version", action="version", version=f"samhus {__version__} (experimental)")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run_parser = subcommands.add_parser("run", help="Execute a local source file")
    run_parser.add_argument("file", type=Path)
    run_parser.add_argument("--max-steps", type=positive_int, default=100_000,
                            help="Execution budget (default: 100000); not a security sandbox")
    run_parser.add_argument("--typecheck", action="store_true", help="Run experimental static type checker first")
    run_parser.add_argument("--optimize", action="store_true",
                            help="Enable safe experimental IR literal folding (requires --backend ir)")
    run_parser.add_argument("--backend", choices=("tree", "vm", "ir"), default="tree",
                            help="Execution backend: tree, VM, or verified IR lowered to VM (default: tree)")
    check_parser = subcommands.add_parser("check", help="Check syntax only (not types)")
    check_parser.add_argument("file", type=Path)
    type_parser = subcommands.add_parser("typecheck", help="Check experimental static types")
    type_parser.add_argument("file", type=Path)
    ast_parser = subcommands.add_parser("ast", help="Print a JSON syntax tree")
    ast_parser.add_argument("file", type=Path)
    fmt_parser = subcommands.add_parser("fmt", help="Format experimental Samhus source")
    fmt_parser.add_argument("file", type=Path)
    fmt_flags = fmt_parser.add_mutually_exclusive_group()
    fmt_flags.add_argument("--check", action="store_true", help="Fail if formatting differs")
    fmt_flags.add_argument("--write", action="store_true", help="Rewrite the file in place")
    ir_parser = subcommands.add_parser("ir", help="Inspect validated basic-block IR, stack and scope states")
    ir_parser.add_argument("file", type=Path)
    ir_parser.add_argument("--types", action="store_true", help="Show experimental stack value types (requires static checker)")
    ir_parser.add_argument("--optimize", action="store_true",
                           help="Show verified IR after pure literal folding")
    disasm_parser = subcommands.add_parser("disasm", help="Inspect experimental compiled bytecode")
    disasm_parser.add_argument("file", type=Path)
    emit_parser = subcommands.add_parser("emit-c", help="Generate C11 source from experimental typed subset")
    emit_parser.add_argument("file", type=Path)
    native_parser = subcommands.add_parser("native", help="Build standalone executable using system C compiler")
    native_parser.add_argument("file", type=Path)
    native_parser.add_argument("-o", "--output", required=True, type=Path)
    native_parser.add_argument("--cc", default=None, help="Compiler executable (default: cc/gcc/clang)")
    args = parser.parse_args(argv)
    if args.command == "run" and args.optimize and args.backend != "ir":
        parser.error("--optimize requires --backend ir")
    if args.command == "ir" and args.optimize and args.types:
        parser.error("--optimize and --types cannot be combined in this prototype")
    try:
        program = None if args.command == "fmt" else load_program(args.file)
        if args.command == "check":
            print(f"Syntax OK: {args.file}")
        elif args.command == "typecheck":
            TypeChecker(program).check()
            print(f"Type check OK: {args.file}")
        elif args.command == "ast":
            print(dump_program(program))
        elif args.command == "emit-c":
            sys.stdout.write(emit_program_c(program))
        elif args.command == "native":
            compiled = emit_program_c(program)
            compiler = args.cc or next((name for name in ("cc", "gcc", "clang") if shutil.which(name)), None)
            if compiler is None or shutil.which(compiler) is None:
                print("samhus: no C compiler found (cc/gcc/clang required)", file=sys.stderr)
                return 1
            with tempfile.TemporaryDirectory(prefix="samhus-native-") as temp:
                c_file = Path(temp) / "program.c"
                c_file.write_text(compiled, encoding="utf-8")
                output = args.output.resolve()
                result = subprocess.run(
                    [compiler, "-std=c11", "-O2", str(c_file), "-o", str(output)],
                    text=True, capture_output=True, check=False,
                )
                if result.returncode != 0:
                    print("samhus: native C compiler failed:", file=sys.stderr)
                    print(result.stderr, file=sys.stderr)
                    return 1
                print(f"Native executable: {output}")
        elif args.command == "disasm":
            sys.stdout.write(compile_ast(program).disassemble())
        elif args.command == "ir":
            if args.optimize:
                from .optimizer import optimize_ir
                optimized, _stats = optimize_ir(compile_ir(program))
                sys.stdout.write(optimized.disassemble())
            elif args.types:
                from .typed_ir import compile_typed_ir
                sys.stdout.write(compile_typed_ir(program).disassemble())
            else:
                sys.stdout.write(compile_ir(program).disassemble())
        elif args.command == "fmt":
            source = args.file.read_text(encoding="utf-8")
            formatted = format_program(source)
            if args.check:
                if source != formatted:
                    print(f"Needs formatting: {args.file}", file=sys.stderr)
                    return 1
                print(f"Formatting OK: {args.file}")
            elif args.write:
                if contains_comments(source):
                    print("Refusing to overwrite source containing comments: formatter does not preserve comments", file=sys.stderr)
                    return 1
                args.file.write_text(formatted, encoding="utf-8")
                print(f"Formatted: {args.file}")
            else:
                sys.stdout.write(formatted)
        else:
            if args.typecheck:
                TypeChecker(program).check()
            if args.backend == "vm":
                VirtualMachine(sys.stdout, max_steps=args.max_steps).run(compile_ast(program))
            elif args.backend == "ir":
                intermediate = compile_ir(program)
                if args.optimize:
                    from .optimizer import optimize_ir
                    intermediate, _stats = optimize_ir(intermediate)
                VirtualMachine(sys.stdout, max_steps=args.max_steps).run(
                    lower_ir(intermediate)
                )
            else:
                Interpreter(sys.stdout, max_steps=args.max_steps).run(program)
        return 0
    except (OSError, UnicodeError) as exc:
        print(f"samhus: {exc}", file=sys.stderr)
        return 1
    except SamhusError as exc:
        print(f"{args.file}:{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
