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

## Status

Early design. The language is specified in [`docs/spec.md`](docs/spec.md); there
is no implementation yet. The deterministic canonical-to-Python core is the next
build target.

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
