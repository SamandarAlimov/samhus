"""Run with: python -m samhus run examples/hello.sahu"""
import argparse
from pathlib import Path
import sys

from . import __version__, parse, run, SamhusError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="samhus", description="Samhus experimental interpreter")
    parser.add_argument("--version", action="version", version=f"samhus {__version__} (experimental)")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "check"):
        command = subcommands.add_parser(name)
        command.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        source = args.file.read_text(encoding="utf-8")
        if args.command == "check":
            parse(source)
            print(f"Syntax OK: {args.file}")
        else:
            run(source)
        return 0
    except (OSError, UnicodeError) as exc:
        print(f"samhus: {exc}", file=sys.stderr)
        return 1
    except SamhusError as exc:
        print(f"{args.file}:{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
