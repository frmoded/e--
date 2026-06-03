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
- `{{ ... }}` LLM value slots **are** runnable — see "Resolving `{{ }}` slots"
  below for the one-time setup. Files with no slots (like
  `examples/describe.emm`) need no key and `--run` works with no model.

## Resolving `{{ }}` slots (LLM setup)

A `{{ ... }}` slot is an English phrase that the transpiler resolves to a Python
expression **once, at transpile time**, using an LLM — then caches the result so
later builds are offline and reproducible. Files with **no** `{{ }}` slots need
no API key and no setup.

To run a slot example end to end:

```
# 1. create and activate a virtual env
python3 -m venv .venv && source .venv/bin/activate

# 2. install dependencies (the Anthropic SDK)
pip install -r requirements.txt

# 3. set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. transpile and run a slot example
python3 src/transpiler.py examples/primes.emm --run
```

The first run calls the model (Anthropic Haiku) to resolve each slot, writes the
resolved Python expression to **`.emm_cache.json`**, and bakes it into the
output. Every later run is an **offline cache hit** — no model call, identical
result. The cache file maps the exact slot text to its resolved expression and
is meant to be **committed**, so resolved values stay diffable and reviewable.

Editing a slot's text is a cache miss and re-resolves; deleting the cache forces
full re-resolution. Files without `{{ }}` slots (like `examples/describe.emm`)
never touch the API.

## Writing in free English

You don't have to write canonical E-- by hand. The transpiler's first phase
**normalizes** free-English E-- into canonical E-- with an LLM, then compiles
the canonical form to Python — one input, two outputs. An English source
(`examples/describe_en.en`) reads like prose:

```
Define a function called describe that takes a number n. If n is greater than
ten, give back the string "big". Otherwise, give back the string "small".
Then, for each n in the list 3, 42 and 7, print describe of n.
```

Normalize it to canonical and run the result, saving the canonical form too:

```
python3 src/transpiler.py examples/describe_en.en --canonical-out out.em --run
```

`out.em` holds the canonical E-- (equivalent to `examples/describe.emm`) and the
program prints `small / big / small`.

Two properties make this safe and cheap:

- **The parser is the canonical-detector.** Whether a file "is already
  canonical" is decided by trying to parse it deterministically — no LLM, no
  heuristic. An **already-canonical file needs no API key**: normalization
  short-circuits before any model call. Only genuinely English input hits the
  model.
- **Fixed point + cache.** Feeding the canonical output (`out.em`) back in
  parses as canonical, so Phase 1 does nothing and reproduces the same outputs.
  Normalizations are cached in a committed `.emm_norm_cache.json` (keyed by
  source text), so re-running English input is an offline cache hit. Setup is
  the same as for slots: `pip install -r requirements.txt` and
  `export ANTHROPIC_API_KEY=...`.

Normalization and `{{ }}` slot resolution are independent, separately cached LLM
touchpoints — a canonical file with all slots cached makes **zero** live calls.

## Status

Early design. The language is specified in [`docs/spec.md`](docs/spec.md). The
deterministic canonical-to-Python core (lexer, parser, emitter) is implemented
with a runnable CLI — see "Running E--" above — and `{{ }}` slot resolution is
wired up (Anthropic Haiku + a committed cache; see "Resolving `{{ }}` slots").
The LLM normalizer (free English → canonical) is wired up at whole-file
granularity (see "Writing in free English"); per-region normalization is the
next refinement.

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
