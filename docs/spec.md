# E-- (English--) — Language Specification

**Version:** 0.1 (draft)
**Status:** design — no implementation yet
**License:** Apache 2.0

E-- is a programming language whose source code is written in a *canonical,
controlled subset of English*. It is designed to read and edit like plain
English, while compiling **deterministically** to Python. "English--" because
it is English with the ambiguity removed: a closed grammar and a fixed
vocabulary, with exactly one canonical phrasing per construct.

This document is the source of truth for the language. It is **append-mostly**:
add clauses, do not restructure existing prose unless a major version bump is
explicitly happening.

---

## 1. Architecture

E-- runs as a two-stage pipeline with deliberately different reliability
profiles:

```
Free English  --LLM (fuzzy, transpile-time)-->  Canonical E--  --plain parser (deterministic)-->  Python
```

- **Normalizer (LLM, optional front-end).** Turns free-form English into
  canonical E--. This is the only stage that has to deal with linguistic
  ambiguity.
- **Compiler (deterministic core).** Turns canonical E-- into Python with an
  ordinary parser — recursive descent, no LLM, fully reproducible and
  debuggable.

The pipeline also runs backward: Python → canonical E-- is a plain
pretty-printer, so any Python program can be rendered as editable English.

### 1.1 The determinism contract

The structure of a program (what is a statement, a call, a variable, a loop) is
**always** resolved by the deterministic parser. The LLM is **never** allowed to
decide structure. The LLM is invoked only to fill clearly-delimited *value
slots* (see §4.4).

### 1.2 LLM is transpile-time only (HARD RULE)

The LLM is called **only at transpile time** — never at runtime. Generated
Python is always pure and contains no model calls. There are exactly two
transpile-time LLM jobs:

1. Normalizing free English → canonical E-- (§1, optional).
2. Resolving `{{ ... }}` value slots into literals (§4.4).

After transpiling, the produced Python is self-contained and deterministic.

---

## 2. Canonical form principles

- **Closed vocabulary.** Exactly one canonical phrasing per construct
  (`is greater than`, never `exceeds` / `is bigger than`). The normalizer
  collapses the infinite English variants into the single canonical phrasing;
  the parser only ever sees that one.
- **Explicit markers carry precision.** The parser never guesses whether a token
  is a value, a variable, or a call — markers disambiguate (§3).
- **Canonical is the source of truth.** Edit the canonical, regenerate Python.
  The free-English layer is a convenience entry point, not something kept in
  sync.

---

## 3. Notation and markers

Every token's role is made explicit by its marker, so the parser is never forced
to infer category:

| Marker          | Meaning                          | Example                         |
|-----------------|----------------------------------|---------------------------------|
| `[[name]]`      | function name / call             | `[[print]]`, `[[fibonacci]]`    |
| bare word       | variable                         | `year`, `total`                 |
| `3`, `3.5`      | numeric literal                  | `42`, `-1`, `3.14`              |
| `"text"`        | string literal                   | `"hello"`                       |
| `<a, b, c>`     | list                             | `<1, 2, 3>`                     |
| `{}` / `{k: v}` | dict / map                       | `{}`, `{"a": 1}`                |
| `True` `False`  | booleans                         | `True`, `False`                 |
| `Nothing`       | null                             | (compiles to Python `None`)     |
| `{{ text }}`    | LLM-resolved value slot          | `{{the first prime over 5}}`    |

Design notes:

- **Lists use angle brackets** `<...>` specifically to avoid collision with the
  `[[...]]` call syntax. Angle brackets are free because comparisons are written
  in English (`is greater than`), not with `<` / `>`.
- **LLM slots use double curly braces** `{{...}}` to avoid colliding with call
  argument parentheses `(...)`. Doubled braces stay visually distinct from the
  single-brace dict literal `{...}`, and pair naturally against `[[...]]` for
  calls ("`[[ ]]` is a call, `{{ }}` is fill-this-in").

---

## 4. Expressions

An **expression** produces a value. The grammar is recursive:

```
expression  := literal
             | variable
             | call
             | llm-slot
             | infix-chain
             | collection
literal      := number | string | True | False | Nothing
variable     := bare-word
call         := "[[" name "]]" "(" arg-list? ")"
arg-list     := expression ( "," expression )*
llm-slot     := "{{" free-text "}}"
collection   := list | dict
list         := "<" ( expression ( "," expression )* )? ">"
dict         := "{" ( entry ( "," entry )* )? "}"
entry        := expression ":" expression
infix-chain  := expression infix-op expression
```

### 4.1 Function calls (Option 2: arguments are expressions)

A function call is `[[name]]( arg-list )`, where **each argument is itself an
expression**. This is the central design choice: because arguments are
expressions (not just atoms), nesting and composition fall out for free with no
special-case machinery.

```
[[print]](year)                         print(year)
[[fibonacci]](3)                        fibonacci(3)
[[add]](a, b)                           add(a, b)
[[max]](<1, 2, 3>)                      max([1, 2, 3])
```

### 4.2 Nesting

Because an argument is an expression, a nested call is just an argument that
happens to be a call. Parentheses make the structure unambiguous:

```
f(g(3), 2)        →   [[f]]([[g]](3), 2)
f(g(3, 2))        →   [[f]]([[g]](3, 2))
h(f(x), g(y))     →   [[h]]([[f]](x), [[g]](y))
```

The parser is plain recursive descent; no heuristic is needed to find argument
boundaries because every call delimits its own argument list with `( )`.

### 4.3 Infix operators

Arithmetic and comparison may be written as infix English operator chains. (The
exact operator vocabulary and precedence table is an open item — see §8.)
Indicative forms:

```
a plus b                a + b
a minus b               a - b
a times b               a * b
a is greater than b     a > b
a is less than b        a < b
a equals b              a == b
```

Operators and function calls may be freely mixed; an operand may be any
expression, including a call or an LLM slot.

### 4.4 LLM value slots `{{ ... }}`

A `{{ ... }}` slot is free English that the **LLM resolves to a value at
transpile time**. The resolved value is baked into the generated Python as a
literal. A slot may appear anywhere an expression may appear, including as a
call argument:

```
[[fibonacci]]( {{the first prime number greater than 5}} )
For each year in {{all 20th century prime years}}:
    Do [[print]](year).
```

Transpiles (illustratively) to:

```python
fibonacci(7)
for year in [1901, 1907, 1913, ...]:
    print(year)
```

#### 4.4.1 Caching (freeze-by-cache)

`{{ ... }}` slots stay in the canonical source (so the source remains readable,
editable English). Resolution is **cached, keyed by the exact slot text**
(`phrase -> value`):

- First transpile: LLM resolves the slot; value is cached and baked into Python.
- Re-transpile, unchanged slot text: **cache hit**, same literal, no LLM call,
  no drift.
- Edited slot text: cache miss → re-resolve.
- Clearing the cache forces full re-resolution.

The cache file is plain `phrase -> value`, diffable and committable. The cache
**is** the freeze: canonical stays live English while builds stay reproducible.

---

## 5. Statements

Every statement begins with a verb that states its intent. The verb also
resolves the statement-vs-expression question: `Set ... to` keeps a call's
result; `Do` discards it.

```
Set <var> to <expr>.            assignment            v = f(3, 2)
Do <call>.                      call, result discarded print(x)
Give back <expr>.               return                 return expr
If <cond>: ...                  conditional            if cond:
While <cond>: ...               loop                   while cond:
For each <var> in <expr>: ...   loop                   for v in expr:
Define [[f]] taking a, b: ...   function definition    def f(a, b):
```

Example program:

```
Define [[classify]] taking n:
    If n is greater than 0:
        Give back "positive".
    Give back "non-positive".

For each year in {{all 20th century prime years}}:
    Set label to [[classify]](year).
    Do [[print]](label).
```

### 5.1 Statement terminator and blocks

- A simple statement ends with a period `.`.
- A compound statement (`If`, `While`, `For each`, `Define`) ends its header
  with a colon `:` and owns an indented block, mirroring Python.

**Blocks use significant indentation, Python-style** (decided 0.1.1). Block
membership is determined by indentation depth exactly as in Python; there are no
explicit block-delimiter tokens. This maps one-to-one onto the Python target and
keeps canonical E-- visually aligned with its output.

---

## 6. Literals and collections

```
42            42
3.14          3.14
"hello"       "hello"
True          True
False         False
Nothing       None
<1, 2, 3>     [1, 2, 3]
{}            {}
{"a": 1}      {"a": 1}
```

Lists use `<...>`; dicts use `{...}`. Everything else follows Python semantics
unless a future clause states otherwise.

---

## 7. Worked example: end to end

Non-canonical (free English, normalizer input):

> Call function fibonacci with the first prime number greater than 5 and print
> the result.

Canonical E-- (parser input):

```
Set result to [[fibonacci]]( {{the first prime number greater than 5}} ).
Do [[print]](result).
```

Generated Python (deterministic; `{{ }}` baked from cache):

```python
result = fibonacci(7)
print(result)
```

---

## 8. Open questions

- **Operator vocabulary and precedence.** Finalize the canonical infix operator
  set and a precedence table, or require explicit grouping for all mixed-operator
  expressions.
- **Extended verb set.** `break`, `continue`, `import`, exception handling,
  classes — added as future verbs.
- **Constant vs. variable distinction.** Whether a dedicated marker for named
  constants is warranted, or `UPPER_CASE` convention suffices.
- **Normalizer canonicalization guarantees.** How strictly the normalizer must
  round-trip (free English → canonical → same canonical).
- **Cache format and location.** On-disk schema for the `phrase -> value` cache.

---

## Changelog

- **0.1.1** — Block delimitation decided: significant indentation, Python-style
  (§5.1); removed from open questions.
- **0.1** — Initial draft. Architecture, determinism contract, transpile-time-
  only LLM rule, marker notation, Option-2 expression-argument call grammar with
  nesting, `{{ }}` LLM slots with freeze-by-cache, core statement verbs.
