"""Run with: python -m samhus run examples/hello.sahu"""
import argparse
from pathlib import Path
import sys

from . import __version__, parse, run, SamhusError
from .typecheck import check_types
from .astdump import dump_ast


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
    check_parser = subcommands.add_parser("check", help="Check syntax only (not types)")
    check_parser.add_argument("file", type=Path)
    type_parser = subcommands.add_parser("typecheck", help="Check experimental static types")
    type_parser.add_argument("file", type=Path)
    ast_parser = subcommands.add_parser("ast", help="Print a JSON syntax tree")
    ast_parser.add_argument("file", type=Path)
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
        else:
            if args.typecheck:
                check_types(source)
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
