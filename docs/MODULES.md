# Experimental local Samhus modules (unreleased research)

**This is an experimental source-file linker, not a package system.**
The `.sahu` suffix, `import` syntax and all module semantics are provisional.

## Example

```samhus
// examples/modules/main.sahu
import "lib/stats.sahu"

fn main() -> Unit {
    println(double(sum_values([10,20,30])))
}
```

`lib/stats.sahu` imports `math.sahu` from its **own directory**, not
from the current shell working directory. Imported modules define functions;
only the root entry source file may declare `fn main()`.

```bash
python -m samhus run examples/modules/main.sahu --backend tree --typecheck
python -m samhus run examples/modules/main.sahu --backend vm --typecheck
python -m samhus typecheck examples/modules/main.sahu
python -m samhus disasm examples/modules/main.sahu
```

Both execution modes should print **120**.

The restricted C11 native backend can compile a multi-file program only
when all imported functions use its supported typed Int/Bool/String subset:

```bash
python -m samhus native examples/modules/native_main.sahu -o native-demo
./native-demo
```

The native sample prints **42**; compiled executable runs without Python,
but the Samhus compiler **still requires Python and a C compiler**.

## Implementation limitations

- Imports are **literal local paths**: `import "lib/math.sahu"`.
  Files are UTF-8, sourced relative to the importing file.
- All imports are resolved by `samhus FILE` commands, then functions are
  merged into a **flat global symbol table**. This means no qualified
  namespace, aliases, import visibility, package manager or separate ABI.
- A module is loaded once even if imported through multiple branches.
- Duplicate function names, cycles and `main` in an imported module
  are rejected with diagnostics.
- Root is the directory containing the entrypoint source file.
  Imports cannot escape it via relative paths or symlinks, and cannot
  use absolute/network/drive paths or file extensions other than the
  currently provisional `.sahu`.
- Max 64 linked modules, max import depth 16, total imported source
  max 4 million characters, plus per-file parser/lexer guards.
- Libraries may be formatted standalone without `main`; source-string
  APIs such as `run(source)`, `parse_program(source)` reject unresolved
  imports. Use `load_program(path)` to build a linked Program AST.
- Existing `fn main` entrypoint rule is unchanged.
- This isn't a sandbox, secure package manager, reproducible lockfile
  or independent compiler frontend.

## How imports fail

Importing `../other.sahu` outside the root, absolute paths, a symlink
pointing outside root, a cyclic chain or a missing file fails early.
Typechecking imported function signatures also works.
Untrusted imported source is still **unsafe to execute**: resource controls
are incomplete and no OS-level isolation is present.

## Open design choices

Namespacing and symbols, import syntax, extension, stable package format,
dependency policies, visibility and final compiler architecture require
future tests and founder approval. No design decision above is finalized.
