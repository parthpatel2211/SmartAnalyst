"""Guarantees, not features.

These tests encode claims the README makes. If one fails, the README has
become false, and the fix belongs in the code rather than in the test.
"""

import re
from pathlib import Path

BACKEND = Path("backend_app")
SCRIPTS = Path("scripts")

# The lookbehind keeps `re.compile(...)` and other attribute calls out of the
# match; it is the bare builtins that turn a string into running code.
_DYNAMIC_EXECUTION = re.compile(r"(?<![.\w])(exec|eval|compile)\s*\(")
_KEY_SHAPED = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")


def _source_lines(root: Path):
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            yield path, lineno, line


def test_backend_contains_no_dynamic_code_execution():
    """SmartAnalyst answers questions with SQL, never with generated code.

    The prototype passed model output to exec() with __import__ available in
    the builtins it allowed, which made the sandbox decorative. Removing the
    capability entirely is the reason this project can claim what it claims.
    """
    offenders = [
        f"{path}:{lineno}: {line.strip()}"
        for path, lineno, line in _source_lines(BACKEND)
        if not line.strip().startswith("#") and _DYNAMIC_EXECUTION.search(line)
    ]
    assert not offenders, "Dynamic code execution found:\n" + "\n".join(offenders)


def test_no_hardcoded_api_keys_anywhere():
    offenders = [
        f"{path}:{lineno}"
        for root in (BACKEND, SCRIPTS)
        for path, lineno, line in _source_lines(root)
        if _KEY_SHAPED.search(line)
    ]
    assert not offenders, f"Possible hardcoded key at: {offenders}"


def test_the_server_never_reads_an_api_key_from_the_environment():
    """Keys arrive per request. A server-side key would mean the owner pays
    for every stranger's queries and that a leak exposes a real credential."""
    settings_source = (BACKEND / "config.py").read_text(encoding="utf-8")
    assert "api_key" not in settings_source.lower()


def test_the_only_path_to_the_database_runs_through_the_guard():
    """The guard is worthless if a query can reach DuckDB around it.

    Execution is confined to engine.run_query, which validates first. Any new
    conn.execute in application code outside the engine is a second door.
    """
    offenders = [
        f"{path}:{lineno}: {line.strip()}"
        for path, lineno, line in _source_lines(BACKEND)
        if ".execute(" in line and path.name != "engine.py"
    ]
    assert not offenders, (
        "Query execution outside engine.run_query bypasses SQL validation:\n"
        + "\n".join(offenders)
    )


def test_the_guard_is_actually_invoked_by_the_engine():
    engine_source = (BACKEND / "engine.py").read_text(encoding="utf-8")
    assert "validate(sql)" in engine_source
