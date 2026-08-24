"""
Guard against a name that no longer exists.

A refactor once deleted `_auth` and `_get` — the entire HTTP layer of
racing_api — while every other reference to them stayed. Nothing caught it:
the file still parsed, the module still imported, and 295 tests still passed,
because the tests that touch racing_api mock at or above `_get`. The failure
only appeared in production, as a NameError surfacing to users as
"502 Racing data unavailable" on every racecard request.

Python resolves globals at call time, so this class of mistake is invisible
until the line runs. This walks every module in `app` and checks that each
global name its code references actually exists once the module is imported.
`symtable` does the scope resolution, so locals, closures, comprehensions and
function-level imports are classified correctly rather than guessed at.
"""
import builtins
import importlib
import pathlib
import symtable

APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def _referenced_globals(src: str, path: str) -> set:
    """Names the code reads from module scope (never assigned there)."""
    found = set()

    def walk(table):
        for sym in table.get_symbols():
            if sym.is_global() and not sym.is_assigned():
                found.add(sym.get_name())
        for child in table.get_children():
            walk(child)

    walk(symtable.symtable(src, path, "exec"))
    return found


def _module_name(path: pathlib.Path) -> str:
    rel = path.relative_to(APP).with_suffix("")
    return "app." + ".".join(rel.parts).replace(".__init__", "")


def test_every_referenced_global_exists():
    missing = {}
    for path in sorted(APP.rglob("*.py")):
        module = importlib.import_module(_module_name(path))
        unresolved = sorted(
            name
            for name in _referenced_globals(path.read_text(), str(path))
            if not hasattr(module, name) and not hasattr(builtins, name)
        )
        if unresolved:
            missing[_module_name(path)] = unresolved

    assert not missing, (
        "These modules reference global names that do not exist. Each one is a "
        f"NameError waiting for the line to run: {missing}"
    )
