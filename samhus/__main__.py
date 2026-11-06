"""Run with: python -m samhus run examples/hello.sahu"""
import argparse
from pathlib import Path
import sys

from . import __version__, parse, run, SamhusError
from .typecheck import check_types
from .astdump import dump_ast
from .formatter import format_program, contains_comments
from .bytecode import compile_source
from .vm import run_vm
from .native_c import emit_c
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
    run_parser.add_argument("--backend", choices=("tree", "vm"), default="tree",
                            help="Experimental execution backend (default: tree)")
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
    disasm_parser = subcommands.add_parser("disasm", help="Inspect experimental compiled bytecode")
    disasm_parser.add_argument("file", type=Path)
    emit_parser = subcommands.add_parser("emit-c", help="Generate C11 source from experimental typed subset")
    emit_parser.add_argument("file", type=Path)
    native_parser = subcommands.add_parser("native", help="Build standalone executable using system C compiler")
    native_parser.add_argument("file", type=Path)
    native_parser.add_argument("-o", "--output", required=True, type=Path)
    native_parser.add_argument("--cc", default=None, help="Compiler executable (default: cc/gcc/clang)")
    args = parser.parse_args(argv)
    try:
        source = args.file.read_text(encoding="utf-8")
        if args.command == "check":
            parse(source)
            print(f"Syntax OK: {args.file}")
        elif args.command == "typecheck":
            check_types(source)
            print(f"Type check OK: {args.file}")
        elif args.command == "ast":
            print(dump_ast(source))
        elif args.command == "emit-c":
            sys.stdout.write(emit_c(source))
        elif args.command == "native":
            compiled = emit_c(source)
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
            sys.stdout.write(compile_source(source).disassemble())
        elif args.command == "fmt":
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
                check_types(source)
            if args.backend == "vm":
                run_vm(source, max_steps=args.max_steps)
            else:
                run(source, max_steps=args.max_steps)
        return 0
    except (OSError, UnicodeError) as exc:
        print(f"samhus: {exc}", file=sys.stderr)
        return 1
    except SamhusError as exc:
        print(f"{args.file}:{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
