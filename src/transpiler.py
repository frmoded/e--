"""E-- transpiler public entry point (deterministic core).

Public API:

    transpile(source: str, resolve_slot=None) -> str

Pipeline: tokenize -> parse -> emit. No network or model calls happen here;
``{{ }}`` slots are resolved through the injected ``resolve_slot`` callable.
If none is provided, a default that raises ``NotImplementedError`` is used, so
a program containing a slot fails loudly rather than silently.

CLI:

    python3 src/transpiler.py path/to/file.emm

prints the transpiled Python. The CLI wires the real Anthropic-backed,
cache-first slot resolver (see ``resolver.make_anthropic_resolver``); files
with no ``{{ }}`` slots transpile with no API key.
"""

from __future__ import annotations

import argparse
import sys

from lexer import tokenize
from parser import parse
from emitter import emit
from errors import EmmSyntaxError, EmmResolveError
from resolver import make_anthropic_resolver


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
    parser.add_argument(
        "-s", "--show", action="store_true",
        help="print the generated Python (even when --run is used)")
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

    # Real {{ }} resolver: cached + Anthropic-backed. Slot-free files never
    # invoke it, so they transpile with no API key.
    resolve = make_anthropic_resolver()

    # Transpile with friendly errors.
    try:
        python_src = transpile(source, resolve_slot=resolve)
    except EmmSyntaxError as exc:
        print(f"syntax error: {exc}", file=sys.stderr)
        return 1
    except EmmResolveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(python_src + "\n")

    if args.run and args.show:
        # Show the code and run it, separated by copy-pasteable comment lines.
        print("# --- generated Python ---")
        print(python_src)
        print("# --- output ---")
        exec(compile(python_src, "<emm>", "exec"), {"__name__": "__main__"})
    elif args.run:
        exec(compile(python_src, "<emm>", "exec"), {"__name__": "__main__"})
    elif args.show:
        print(python_src)
    elif not args.out:
        # Default (no --run / --show / -o): print the generated Python.
        print(python_src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
