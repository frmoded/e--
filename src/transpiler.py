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

import argparse
import sys

from lexer import tokenize
from parser import parse
from emitter import emit
from errors import EmmSyntaxError


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
    parser = argparse.ArgumentParser(
        prog="transpiler.py",
        description="Transpile a canonical E-- (.emm) source file to Python.")
    parser.add_argument(
        "input", help="path to the E-- source file (.emm)")
    parser.add_argument(
        "-o", "--out", metavar="FILE.py",
        help="write the generated Python to FILE.py instead of stdout")
    parser.add_argument(
        "--run", action="store_true",
        help="execute the generated Python after transpiling")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # Read the source file with friendly errors (no raw traceback).
    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            source = fh.read()
    except FileNotFoundError:
        print(f"error: file not found: {args.input}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not read {args.input}: {exc}", file=sys.stderr)
        return 2

    # Transpile with friendly errors.
    try:
        python_src = transpile(source, resolve_slot=_cli_resolver)
    except EmmSyntaxError as exc:
        print(f"syntax error: {exc}", file=sys.stderr)
        return 1
    except NotImplementedError:
        print(
            "error: this program contains an LLM value slot ({{ ... }}) that "
            "cannot be run yet.\n"
            "LLM slot resolution is not implemented; remove the slot or wait "
            "for resolver support.",
            file=sys.stderr)
        return 1

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(python_src + "\n")
    if args.run:
        exec(compile(python_src, "<emm>", "exec"), {"__name__": "__main__"})
    if not args.out and not args.run:
        print(python_src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
