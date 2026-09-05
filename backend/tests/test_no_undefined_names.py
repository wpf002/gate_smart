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
import ast
import builtins
import importlib
import pathlib
import symtable

BACKEND = pathlib.Path(__file__).resolve().parent.parent
APP = BACKEND / "app"
# The nightly jobs live in scripts/ and were NOT covered. They are the least
# exercised code in the repo — nothing imports them, no test calls them, and a
# failure surfaces only as a job that quietly did nothing overnight. That is
# exactly where a deleted-but-referenced name hides longest.
SCRIPTS = BACKEND / "scripts"


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


def _script_globals(path: pathlib.Path) -> set:
    """Names a script defines at module level, without importing it.

    Scripts run argparse and load dotenv at import, so they are parsed rather
    than imported. Anything referenced but not defined here, imported here, or
    built in, is a NameError waiting for that branch to run.
    """
    tree = ast.parse(path.read_text(), str(path))
    # Module dunders exist at runtime without ever being assigned.
    defined = {"__file__", "__name__", "__doc__", "__package__", "__spec__"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                defined.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, ast.Global):
            defined.update(node.names)
    return defined


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


def test_scripts_reference_no_undefined_names():
    """Same guard, extended to the nightly jobs.

    scripts/ is where the least-exercised code lives: nothing imports it, no
    test calls it, and a NameError there shows up as a job that silently did
    nothing overnight rather than as an error anyone sees.
    """
    missing = {}
    for path in sorted(SCRIPTS.glob("*.py")):
        source = path.read_text()
        defined = _script_globals(path)
        unresolved = sorted(
            name
            for name in _referenced_globals(source, str(path))
            if name not in defined and not hasattr(builtins, name)
        )
        if unresolved:
            missing[path.name] = unresolved

    assert not missing, (
        "These scripts reference names that are never defined or imported in "
        f"them. Each is a NameError waiting for that branch to run: {missing}"
    )
