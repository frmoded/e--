# E-- (English--) — Language Specification

**Version:** 0.1.6 (draft)
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

1. Normalizing free English → canonical E-- (§1.3).
2. Resolving `{{ ... }}` value slots (§4.4).

After transpiling, the produced Python is self-contained and deterministic.

### 1.3 Integrated pipeline: one input, two outputs (decided 0.1.6)

Normalization is **not a separate tool** — it is the first phase of transpile.
The transpiler is a pure function from one input file to two outputs:

```
input (E--, anywhere on the English↔canonical spectrum)
   │
   ├─ Phase 1 — normalize (region by region):
   │     try to parse each region as canonical (deterministic, no LLM)
   │        parses  → keep as-is
   │        fails   → English → normalize via LLM (cached) → canonical
   │   ▶ output A: the canonical E-- form
   │
   └─ Phase 2 — codegen (canonical → Python):
         deterministic, line-at-a-time, no LLM for structure
         {{ }} slots resolved via LLM (cached, §4.4)
       ▶ output B: Python
```

**The parser is the canonical-detector.** Whether a region is "already
canonical" is decided by trying to parse it — no LLM, no heuristic. Canonical's
rigid markers (`[[ ]]`, the fixed verbs) mean real English prose effectively
never parses by accident, so a parse success reliably means "canonical." English
regions (runs of non-parsing lines) are sent to the normalizer together, so
multi-line English keeps the context it needs.

**"Canonical" and "needs an LLM" are independent questions.** A `{{ }}` slot is
valid canonical syntax: a slot-bearing file passes the canonical check and skips
normalization, yet still needs an LLM call at codegen to resolve the slot. So the
two LLM touchpoints are independent, and both are cached (freeze-by-cache):

| Touchpoint | Fires on | Phase | Cached by |
|---|---|---|---|
| Normalize | non-canonical (English) regions | 1 | English region text → canonical |
| Slot resolution | `{{ }}` slots | 2 | slot text → Python expression (§4.4.1) |

A file that is already canonical with all slots cached makes **zero live LLM
calls**. Feeding the canonical output (output A) back in is a **fixed point**: it
parses as canonical, so Phase 1 does nothing and the same outputs are reproduced.

**Workflow is the caller's responsibility.** The transpiler does not manage file
names or the edit loop. It takes an input and produces the canonical form plus
Python; the caller decides what to keep, commit, edit, or feed back in (e.g.
adopting the canonical output as the next input — the steady state is a caller
choice, not a tool opinion).

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
expression  := operand
             | infix-chain
operand      := literal
             | variable
             | call
             | llm-slot
             | collection
             | group
literal      := number | string | True | False | Nothing
variable     := bare-word
call         := "[[" name "]]" "(" arg-list? ")"
arg-list     := expression ( "," expression )*
llm-slot     := "{{" free-text "}}"
collection   := list | dict
list         := "<" ( expression ( "," expression )* )? ">"
dict         := "{" ( entry ( "," entry )* )? "}"
entry        := expression ":" expression
group        := "(" expression ")"
infix-chain  := operand infix-op operand ( infix-op operand )*   ; one operator only — see §4.3
```

**Grouping vs. call parentheses.** A `(` means *call arguments* only when it
immediately follows a `]]` (i.e. `[[name]]( ... )`). A `(` in any other position
is **grouping** — `( expression )` — exactly as Python overloads parentheses.
The parser distinguishes the two by whether the `(` directly follows the call
marker.

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

### 4.3 Infix operators and grouping (no precedence — explicit grouping on mix)

Operators are written as infix English. The canonical vocabulary (v1):

```
arithmetic:   a plus b            a + b
              a minus b           a - b
              a times b           a * b
              a divided by b      a / b
              a modulo b          a % b
              a to the power of b a ** b
comparison:   a is greater than b a > b
              a is less than b    a < b
              a is at least b     a >= b
              a is at most b      a <= b
              a equals b          a == b
              a does not equal b  a != b
boolean:      a and b             a and b
              a or b              a or b
              not a               not a       (prefix; applies to the operand to its right)
membership:   a is in b           a in b
              a is not in b       a not in b
```

**No operator precedence. Grouping is mandatory when operators are mixed.**
E-- deliberately has **no precedence table** — the language's promise is that a
reader never has to recall hidden binding rules. The rule is:

1. A flat chain of **one and the same** operator needs no grouping:
   `a plus b plus c`, `a and b and c`.
2. **Mixing two different operators in one expression is a syntax error** unless
   the intent is made explicit with grouping parentheses `( … )`.

Examples:

```
2 plus 3 times 4              →  SYNTAX ERROR (ambiguous: which binds first?)
(2 plus 3) times 4           →  (2 + 3) * 4   = 20
2 plus (3 times 4)           →  2 + (3 * 4)   = 14

a and b or c                 →  SYNTAX ERROR
(a and b) or c               →  (a and b) or c
a and (b or c)               →  a and (b or c)

(a is greater than b) and (c is less than d)   →  (a > b) and (c < d)
```

`not` is prefix and binds only to the single operand immediately to its right.
Combining its result with an infix operator still requires grouping, and the
rule is **symmetric** — `not` may not sit on *either* side of an infix operator
without grouping. (Allowing bare `not` next to an infix operator would assert a
precedence of `not` over that operator, which the no-precedence rule forbids;
this also matches Python, which rejects `a == not b`.) A bare `not x` standing
alone, with no surrounding infix operator, needs no grouping.

```
not a equals b               →  SYNTAX ERROR   (not on the left, ungrouped)
(not a) equals b             →  (not a) == b
not (a equals b)             →  not (a == b)

a equals not b               →  SYNTAX ERROR   (not on the right, ungrouped)
a equals (not b)             →  a == (not b)

not a                        →  not a          (standalone — no grouping needed)
```

Operands may be any expression — a literal, variable, call, LLM slot, list/dict,
or a parenthesized group — so operators, calls, and `{{ }}` slots compose freely
as long as mixed operators are grouped:

```
[[score]](x) plus 1                          score(x) + 1
({{the base rate}} times count) plus offset  (<llm> * count) + offset
```

The deterministic consequence: the parser never guesses binding. Either an
expression is an unambiguous single-operator chain, or it is fully parenthesized,
or it is rejected.

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

The cache is a JSON file (default `.emm_cache.json` in the working directory): an
object mapping the **exact slot text** to the resolved **Python-expression
string**. It is **committed to git** so builds are reproducible offline and the
resolved values are diffable and auditable. The cache **is** the freeze:
canonical stays live English while builds stay reproducible.

#### 4.4.2 Resolver implementation (LLM)

The resolver is a `resolve_slot(text) -> str` callable, invoked at transpile time
for each `{{ text }}` slot. The reference implementation:

- Uses the Anthropic API, model **`claude-haiku-4-5-20251001`** by default
  (cheapest/fastest; slot resolution is small and factual).
- Instructs the model to return **only a single Python expression** representing
  the value — no prose, no code fences.
- Slots may resolve to **any Python expression**, not only literals.
- Validates the returned string parses as a Python expression
  (`ast.parse(s, mode="eval")`) before baking it. The expression is **not
  executed at transpile time** — it is only run if/when the generated Python is
  run. Invalid (non-parsing) responses raise an error.
- Reads the API key from the `ANTHROPIC_API_KEY` environment variable; a missing
  key when a slot needs resolving is a clear, actionable error.
- Caches results per §4.4.1, so a key is only needed the first time a given slot
  text is seen.

**Safety trade-off.** Because slots may resolve to arbitrary expressions (not
just literals), the model can place executable code into the generated Python.
This is a deliberate power-for-safety trade chosen for E--. Mitigations: the
expression is validated as parseable but never executed at transpile time, and
the cache is committed and diffable, so every baked value is reviewable in
version control before it ever runs.

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
Otherwise if <cond>: ...        else-if branch         elif cond:
Otherwise: ...                  else branch            else:
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
explicit block-delimiter tokens. Indentation/block structure maps one-to-one onto
the Python target, keeping canonical E-- visually aligned with its output.

**Statement-to-line mapping is 1:n, but local** (clarified 0.1.5). A single
canonical statement transpiles to **one or more** Python lines — e.g. a `{{ }}`
slot whose value is rendered across multiple lines. The count is not fixed at
one. What *is* guaranteed is **locality**: a statement's emitted Python depends
only on that statement and its indentation level, never on other lines. This is
what lets canonical→Python codegen run **one canonical line at a time, with no
LLM** — the n emitted lines are a contiguous block at one known indent. (Slots
remain single *expressions*; 1:n refers to emission formatting, not to a slot
introducing multiple statements.)

### 5.2 Conditionals (`If` / `Otherwise if` / `Otherwise`)

An `If` block may be followed by zero or more `Otherwise if <cond>:` branches and
an optional final `Otherwise:` branch. The continuation keywords sit at the **same
indentation as their `If`** and each own an indented block. This maps directly
onto Python `if` / `elif` / `else`.

```
If score is at least 90:
    Set grade to "A".
Otherwise if score is at least 80:
    Set grade to "B".
Otherwise if score is at least 70:
    Set grade to "C".
Otherwise:
    Set grade to "F".
```
→
```python
if score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 70:
    grade = "C"
else:
    grade = "F"
```

Rules:

- `Otherwise if` / `Otherwise` are only valid immediately following an `If` (or a
  preceding `Otherwise if`) at matching indentation. A dangling `Otherwise` with
  no governing `If` is a syntax error.
- At most one `Otherwise:` per `If` chain, and it must come last.
- Each branch body is an indented block (§5.1) with at least one statement.

### 5.3 Function definitions

```
Define [[name]] taking <params>:
    <body>
```

- **Parameters** are bare names, comma-separated: `taking a, b, c`.
- **Zero parameters** are written explicitly as `taking nothing`:

  ```
  Define [[banner]] taking nothing:        def banner():
      Do [[print]]("===").                     print("===")
  ```

- **Default values** use `defaulting to <expr>` after a parameter:

  ```
  Define [[greet]] taking name defaulting to "world":
      Do [[print]](name).
  ```
  →
  ```python
  def greet(name="world"):
      print(name)
  ```

  Parameters with defaults follow the same ordering constraint as Python
  (defaulted parameters come after non-defaulted ones).

- **Body** is an indented block (§5.1). **Return** is `Give back <expr>.`;
  falling off the end returns `None`, as in Python.

Note the deliberate asymmetry: parameters in a *definition* are plain names,
while arguments in a *call* are full expressions (`[[f]](a, b plus 1)`). This
mirrors Python's own `def f(a, b)` vs. `f(a, b + 1)` split.

**Deferred to a later clause** (not in v1): variadic parameters (`*args` /
`**kwargs`), keyword-only parameters, type hints / annotations, nested function
definitions, and decorators. See §8.

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

- **Extended verb set.** `break`, `continue`, `import`, exception handling,
  classes — added as future verbs.
- **Extended function features.** Variadic params (`*args` / `**kwargs`),
  keyword-only params, type hints / annotations, nested function definitions,
  decorators (see §5.3).
- **Constant vs. variable distinction.** Whether a dedicated marker for named
  constants is warranted, or `UPPER_CASE` convention suffices.
- **Normalizer canonicalization guarantees.** How strictly the normalizer must
  round-trip (free English → canonical → same canonical).

---

## Changelog

- **0.1.6** — Normalization integrated into transpile (§1.3): one input → two
  outputs (canonical + Python). Parser-as-canonical-detector; English regions
  normalized via LLM (cached), canonical regions pass through. Two independent,
  cached LLM touchpoints (normalize, slot resolution); canonical+cached input →
  zero live LLM calls; canonical output is a fixed point. Filenames/steady-state
  are the caller's responsibility.
- **0.1.5** — Clarified statement-to-Python mapping (§5.1): it is **1:n, but
  local** (was loosely described as one-to-one). Locality — a statement's output
  depends only on that statement and its indent — is what enables line-at-a-time,
  no-LLM codegen.
- **0.1.4** — `{{ }}` resolver specified (§4.4.2): Anthropic Haiku by default,
  returns a single Python expression (any expression, validated by `ast.parse`
  but not executed at transpile time), key via `ANTHROPIC_API_KEY`. Cache format
  fixed (§4.4.1): committed JSON `.emm_cache.json` mapping slot text → expression
  string. Cache-format open question resolved.
- **0.1.3** — `not` rule made symmetric (§4.3): `not` may not sit on either side
  of an infix operator without grouping. Added conditionals (§5.2): `Otherwise
  if <cond>:` → `elif`, `Otherwise:` → `else`, attached to a governing `If` at
  matching indentation. Function definitions renumbered §5.2 → §5.3.
- **0.1.2** — Operators finalized (§4.3): canonical infix vocabulary
  (arithmetic, comparison, boolean, membership) with **no precedence** —
  mixing different operators requires explicit grouping `( )`, else syntax
  error. Added grouping to the grammar (§4) and the call-paren-vs-grouping
  disambiguation rule. Function definitions finalized (§5.2): `taking nothing`
  for zero params, `defaulting to <expr>` for defaults; variadic/keyword-only/
  type-hints/nested-defs/decorators deferred. Operator open question resolved.
- **0.1.1** — Block delimitation decided: significant indentation, Python-style
  (§5.1); removed from open questions.
- **0.1** — Initial draft. Architecture, determinism contract, transpile-time-
  only LLM rule, marker notation, Option-2 expression-argument call grammar with
  nesting, `{{ }}` LLM slots with freeze-by-cache, core statement verbs.
