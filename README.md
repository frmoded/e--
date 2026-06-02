# E-- (English--)

> A programming language you write in plain, canonical English — and that
> compiles **deterministically** to Python.

E-- ("English--") is English with the ambiguity removed: a closed grammar and a
fixed vocabulary, with exactly one canonical phrasing per construct. It is meant
to read and edit like English while still compiling to ordinary, reproducible
Python.

## How it works

E-- is a two-stage pipeline, split so that the unreliable part and the
deterministic part never mix:

```
Free English  --LLM (transpile-time)-->  Canonical E--  --plain parser-->  Python
```

- **Normalizer (LLM, optional).** Turns free-form English into canonical E--.
  This is the only stage that deals with linguistic ambiguity.
- **Compiler (deterministic).** Turns canonical E-- into Python with an ordinary
  parser — no LLM, fully reproducible and debuggable.

**The LLM runs only at transpile time, never at runtime.** Generated Python is
always pure and self-contained. The LLM is never allowed to decide program
structure; it is used only to fill clearly-delimited value slots written as
`{{ ... }}`, and those resolutions are cached so builds stay reproducible.

## A taste

Canonical E--:

```
Set result to [[fibonacci]]( {{the first prime number greater than 5}} ).
Do [[print]](result).
```

compiles to:

```python
result = fibonacci(7)
print(result)
```

Markers keep it unambiguous: `[[name]]` is a function call, a bare word is a
variable, `"x"`/`3` are literals, `<1, 2, 3>` is a list, and `{{ ... }}` is an
English phrase the transpiler resolves once and bakes in.

## Running E--

E-- source files use the **`.emm`** extension (English--). The deterministic
canonical-to-Python core is implemented; you can transpile and run `.emm` files
from the command line.

Transpile a file and print the generated Python to your screen:

```
python3 src/transpiler.py examples/describe.emm
```

prints:

```python
def describe(n):
    if n > 10:
        return "big"
    return "small"
for n in [3, 42, 7]:
    print(describe(n))
```

Write the generated Python to a file instead of the screen:

```
python3 src/transpiler.py examples/describe.emm -o out.py
```

Transpile **and run** it, so you see the program's actual output:

```
python3 src/transpiler.py examples/describe.emm --run
```

prints:

```
small
big
small
```

See the generated Python **and** run it in one go with `--show` (alias `-s`):

```
python3 src/transpiler.py examples/describe.emm --run --show
```

prints the code and its output, separated by comment lines:

```
# --- generated Python ---
def describe(n):
    if n > 10:
        return "big"
    return "small"
for n in [3, 42, 7]:
    print(describe(n))
# --- output ---
small
big
small
```

The delimiters are Python comments, so the whole block stays copy-pasteable.
`--show` on its own (without `--run`) just prints the Python, like the default.

Notes:

- The `.emm` extension is the convention for E-- source files.
- `{{ ... }}` LLM value slots are **not runnable yet** — resolving them needs a
  language model, which is not wired up. A file containing a slot will report a
  clear message rather than crash. The `examples/describe.emm` program uses no
  slots, so `--run` works end to end with no model.

## Status

Early design. The language is specified in [`docs/spec.md`](docs/spec.md). The
deterministic canonical-to-Python core (lexer, parser, emitter) is implemented
with a runnable CLI — see "Running E--" above. The LLM normalizer (free English
→ canonical) and real `{{ }}` slot resolution are not yet built.

## Using E-- in your own software

E-- is licensed under **Apache License 2.0** (see [`LICENSE`](LICENSE)) —
permissive, with an explicit patent grant, so it can be embedded in commercial
products freely.

Two clarifications:

- **The license covers the E-- tooling.** The Python that E-- generates is
  yours — the output is not encumbered by this project's license.
- **The LLM is your own.** E--'s normalizer and `{{ }}` resolution require a
  language model that you supply; that provider's terms are separate from this
  project.

## Docs

- [`docs/spec.md`](docs/spec.md) — the language specification (source of truth).
- [`docs/cowork-protocol.md`](docs/cowork-protocol.md) /
  [`docs/cc-prompt-queue.md`](docs/cc-prompt-queue.md) — internal development
  workflow.
