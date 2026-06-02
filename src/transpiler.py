"""E-- transpiler public entry point (deterministic core).

Public API:

    transpile(source: str, resolve_slot=None) -> str

Pipeline: tokenize -> parse -> emit. No network or model calls happen here;
``{{ }}`` slots are resolved through the injected ``resolve_slot`` callable.
If none is provided, a default that raises ``NotImplementedError`` is used, so
a program containing a slot fails loudly rather than silently.

CLI:

    python3 src/transpiler.py path/to/file.emm

prints the transpiled Python. The CLI wires a tiny PLACEHOLDER slot resolver
(a hardcoded phrase -> literal map) purely for the demo — it is NOT real LLM
resolution.
"""

from __future__ import annotations

import sys

from lexer import tokenize
from parser import parse
from emitter import emit


def _default_resolver(text: str) -> str:
    raise NotImplementedError(
        "LLM slot resolver not wired; pass resolve_slot=...")


def transpile(source: str, resolve_slot=None) -> str:
    """Transpile canonical E-- source to Python source text."""
    if resolve_slot is None:
        resolve_slot = _default_resolver
    tokens = tokenize(source)
    program = parse(tokens)
    return emit(program, resolve_slot)


# --- CLI -----------------------------------------------------------------

# PLACEHOLDER resolver for the CLI demo only. NOT real LLM resolution — a
# hardcoded phrase -> Python-literal map so examples with {{ }} slots run.
_CLI_PLACEHOLDER_SLOTS = {
    "the first prime number greater than 5": "7",
}


def _cli_resolver(text: str) -> str:
    if text in _CLI_PLACEHOLDER_SLOTS:
        return _CLI_PLACEHOLDER_SLOTS[text]
    raise NotImplementedError(
        f"CLI placeholder resolver has no mapping for slot: {text!r}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: python3 src/transpiler.py <file.emm>", file=sys.stderr)
        return 2
    with open(argv[0], "r", encoding="utf-8") as fh:
        source = fh.read()
    print(transpile(source, resolve_slot=_cli_resolver))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
