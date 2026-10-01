"""Fail when the Bruno collection has drifted away from the API client."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CLIENT_PY = REPO / "src" / "aiofarmad" / "client.py"
CONST_PY = REPO / "src" / "aiofarmad" / "const.py"
BRUNO = REPO / ".bruno"
ENV_DIR = BRUNO / "environments"

CHECKED_ENVIRONMENTS = frozenset({"Local", "CI"})

EXEMPT_METHODS = frozenset({"async_close", "async_login"})

MIRROR_RE = re.compile(r"Mirrors FarmadClient::(async_\w+)")


def public_client_methods() -> set[str]:
    """Return the public, non-exempt async method names on FarmadClient."""
    tree = ast.parse(CLIENT_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "FarmadClient":
            return {
                item.name
                for item in node.body
                if isinstance(item, ast.AsyncFunctionDef)
                and not item.name.startswith("_")
                and item.name not in EXEMPT_METHODS
            }
    msg = "FarmadClient not found in client.py"
    raise SystemExit(msg)


def mirrored_client_methods() -> set[str]:
    """Return every client method a Bruno request claims to mirror."""
    mirrored: set[str] = set()
    for path in sorted(BRUNO.rglob("*.yml")):
        if ENV_DIR in path.parents:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        docs = data.get("docs") if isinstance(data, dict) else None
        if not isinstance(docs, str):
            continue
        mirrored.update(MIRROR_RE.findall(docs))
    return mirrored


def environment_variables() -> dict[str, set[str]]:
    """Return the variable values each checked environment defines."""
    environments: dict[str, set[str]] = {}
    for name in sorted(CHECKED_ENVIRONMENTS):
        path = ENV_DIR / f"{name}.yml"
        if not path.is_file():
            msg = f"missing Bruno environment {path}"
            raise SystemExit(msg)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        values: set[str] = set()
        for variable in data.get("variables", []):
            value = variable.get("value")
            if isinstance(value, str):
                values.add(value)
        environments[name] = values
    return environments


def constant_urls() -> list[tuple[str, str]]:
    """Return the (name, url) http(s) constants declared in const.py."""
    tree = ast.parse(CONST_PY.read_text(encoding="utf-8"))
    urls: list[tuple[str, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            continue
        if isinstance(value, str) and value.startswith("https://"):
            urls.append((target.id, value))
    return urls


def main() -> int:
    """Compare the client against the collection and report every drift."""
    failures: list[str] = []

    client_methods = public_client_methods()
    mirrored = mirrored_client_methods()
    missing = client_methods - mirrored
    stale = mirrored - client_methods
    if missing:
        failures.append(f"client methods without a Bruno mirror: {sorted(missing)}")
    if stale:
        failures.append(f"Bruno mirrors without a client method: {sorted(stale)}")

    environments = environment_variables()
    for name, values in environments.items():
        for constant_name, url in constant_urls():
            if url not in values:
                failures.append(f"{name} environment is missing {constant_name} = {url}")

    if failures:
        for failure in failures:
            print(f"drift: {failure}")
        return 1
    print(
        f"no drift: {len(client_methods)} client methods mirrored across "
        f"{len(list(BRUNO.rglob('*.yml')))} collection files"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
