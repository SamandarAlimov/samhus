"""Experimental, confined local multi-file compilation.

Import syntax is provisional: import "relative/file.sahu"
Imports are resolved relative to the importing file, remain confined to the
entry file's directory tree, and merge top-level functions into one Program.
No packages, namespace aliases, network imports or stable module ABI exist.
"""
from pathlib import Path

from .errors import SamhusError
from .lexer import Token
from .parser import Function, Parser, Program

MAX_MODULES = 64
MAX_IMPORT_DEPTH = 16
MAX_COMBINED_SOURCE_CHARS = 4_000_000


def load_program(entry: str | Path) -> Program:
    """Load a local file and all permitted imports into a resolved AST.

    Files are read with UTF-8. Imports cannot escape the entry directory
    through '..' or symlinks. Cycles and duplicate global names are errors.
    Each file is parsed at most once (diamond imports are allowed).
    """
    entry_file = Path(entry).resolve()
    root = entry_file.parent
    loaded: set[Path] = set()
    active: list[Path] = []
    functions: list[Function] = []
    definitions: dict[str, Path] = {}
    source_total = 0

    def label(path: Path) -> str:
        return str(path.relative_to(root)) if path.is_relative_to(root) else path.name

    def visit(file: Path, origin: Token, depth: int, *, imported: bool) -> None:
        nonlocal source_total
        if file in active:
            chain = " -> ".join(label(part) for part in (*active, file))
            raise SamhusError("Cyclic module import: " + chain, origin.line, origin.column)
        if file in loaded:
            return
        if depth > MAX_IMPORT_DEPTH:
            raise SamhusError(
                f"Import depth limit exceeded ({MAX_IMPORT_DEPTH})",
                origin.line, origin.column,
            )
        if len(loaded) + len(active) >= MAX_MODULES:
            raise SamhusError(
                f"Module count limit exceeded ({MAX_MODULES})",
                origin.line, origin.column,
            )
        try:
            code = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SamhusError(
                f"Cannot read module {label(file)!r}: {exc}",
                origin.line, origin.column,
            ) from None
        source_total += len(code)
        if source_total > MAX_COMBINED_SOURCE_CHARS:
            raise SamhusError(
                f"Total imported source exceeds {MAX_COMBINED_SOURCE_CHARS} characters",
                origin.line, origin.column,
            )
        try:
            parsed = Parser(code).parse_program(
                allow_imports=True, require_main=not imported,
            )
        except SamhusError as exc:
            raise SamhusError(
                f"In module {label(file)!r}: {exc.message}",
                exc.line, exc.column,
            ) from None
        if imported and any(fn.name == "main" for fn in parsed.functions):
            main = next(fn for fn in parsed.functions if fn.name == "main")
            raise SamhusError(
                f"Imported module {label(file)!r} must not define main",
                main.token.line, main.token.column,
            )
        active.append(file)
        try:
            for item in parsed.imports:
                name = item.path
                # Restrict imported paths to normalized, local source files.
                # No network, absolute, Windows drive or alternate separators.
                if (not name or "\x00" in name or "\\" in name
                        or ":" in name or Path(name).is_absolute()
                        or Path(name).suffix != ".sahu"):
                    raise SamhusError(
                        f"Invalid local module path: {name!r}",
                        item.token.line, item.token.column,
                    )
                target = (file.parent / name).resolve()
                if not target.is_relative_to(root):
                    raise SamhusError(
                        f"Import escapes project root: {name!r}",
                        item.token.line, item.token.column,
                    )
                visit(target, item.token, depth + 1, imported=True)
            for fn in parsed.functions:
                previous = definitions.get(fn.name)
                if previous is not None:
                    raise SamhusError(
                        f"Duplicate function {fn.name!r} in {label(file)!r}; "
                        f"already defined in {label(previous)!r}",
                        fn.token.line, fn.token.column,
                    )
                definitions[fn.name] = file
                functions.append(fn)
        finally:
            active.pop()
        loaded.add(file)

    visit(entry_file, Token("ENTRY", "", 1, 1), 0, imported=False)
    return Program(tuple(functions))
