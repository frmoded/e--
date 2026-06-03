"""Phase 1 normalizer: free-English E-- -> canonical E-- (spec §1.3).

`make_normalizer(...)` returns a `normalize(source) -> str` callable that turns
a free-English (or mixed) E-- source into canonical E--, at **whole-file**
granularity (the per-region refinement in §1.3 is a later layer):

1. **Canonical detection (no LLM).** Try to ``parse(tokenize(source))`` with the
   deterministic core. If it parses, the source is already canonical — return it
   unchanged, no model call. The parser is the canonical-detector.
2. **Cache hit.** Otherwise consult a committed JSON cache keyed by source text;
   a hit returns the cached canonical string with no model call.
3. **Cache miss.** Ask an Anthropic model (Haiku by default) — whose system
   prompt embeds a concise canonical-E-- reference — for ONLY the canonical
   program, strip defensive code fences, then **validate by re-parsing**. Output
   that does not parse raises ``EmmNormalizeError`` (never silently accepted).
   The validated canonical is cached and returned.

Like the resolver, the model call happens only on a cache miss and the Anthropic
client is constructed lazily — so already-canonical input, cache hits, and the
mock path need neither the ``anthropic`` package nor an API key.
"""

from __future__ import annotations

import json
import os

from lexer import tokenize
from parser import parse
from errors import EmmNormalizeError, EmmSyntaxError

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# A tight-but-complete canonical-E-- reference, drawn from spec §3, §4.3, §5,
# so the model emits valid canonical that the deterministic parser accepts.
_SYSTEM_PROMPT = """\
You translate free-form English into CANONICAL E-- ("English--"), a controlled \
English language that compiles deterministically to Python. Output ONLY the \
canonical E-- program — no prose, no explanation, no markdown code fences.

Canonical E-- is English with the ambiguity removed: a closed grammar, fixed \
verbs, and explicit markers. Significant indentation (Python-style) drives block \
structure; indent nested blocks by 4 spaces. End simple statements with a period.

STATEMENT VERBS (one canonical phrasing each):
- Set <var> to <expr>.                      assignment
- Do <expr>.                                evaluate for effect (e.g. a call)
- Give back <expr>.                         return
- If <cond>:                                if-block (body indented below)
- Otherwise if <cond>:                      elif-block
- Otherwise:                                else-block
- While <cond>:                             while-loop
- For each <var> in <expr>:                 for-loop
- Define [[name]] taking <params>:          function definition (params comma-separated bare words; "taking nothing" or "taking:" for none)

MARKERS:
- [[name]] is a function CALL: [[print]](x), [[describe]](n). A bare word is a VARIABLE.
- Literals: "text" is a string, 3 / 3.5 are numbers, True / False are booleans, Nothing is None.
- <a, b, c> is a LIST. {"k": v} is a DICT. <> is the empty list.
- {{ english phrase }} is an LLM value slot — keep such phrases verbatim inside {{ }} (do not resolve them).

OPERATORS (infix English; NO PRECEDENCE):
  a plus b | a minus b | a times b | a divided by b
  a is greater than b | a is less than b | a does not equal b
  a and b | a or b | not a (prefix)
  a is in b | a is not in b
Grouping rule: a flat chain of ONE repeated operator needs no parentheses \
(a plus b plus c). MIXING two different operators REQUIRES explicit grouping \
with ( ): write (2 plus 3) times 4, never 2 plus 3 times 4. `not` may not sit on \
either side of an infix operator without grouping: (not a) equals b, or \
not (a equals b).

Produce the most direct canonical translation of the user's program. Preserve \
identifiers and string contents. Emit nothing but the canonical program.
"""


def _load_cache(cache_path: str) -> dict:
    if not os.path.exists(cache_path):
        return {}
    with open(cache_path, "r", encoding="utf-8") as fh:
        data = fh.read().strip()
    if not data:
        return {}
    return json.loads(data)


def _write_cache(cache_path: str, cache: dict) -> None:
    with open(cache_path, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, sort_keys=True, indent=2)
        fh.write("\n")


def _strip_fences(text: str) -> str:
    """Defensively remove markdown code fences and surrounding whitespace."""
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _parses_as_canonical(source: str) -> bool:
    """The parser is the canonical-detector: does this source parse cleanly?"""
    try:
        parse(tokenize(source))
        return True
    except EmmSyntaxError:
        return False


def make_normalizer(cache_path: str = ".emm_norm_cache.json",
                    model: str = _DEFAULT_MODEL,
                    client=None):
    """Build a `normalize(source) -> str` whole-file normalizer.

    `client` may be injected (e.g. a fake in tests, or a preconstructed
    Anthropic client); if None, a real client is constructed lazily on the
    first cache miss, requiring ``ANTHROPIC_API_KEY``.
    """
    state = {"client": client}

    def normalize(source: str) -> str:
        # 1. Canonical detection — no LLM, no key, short-circuits everything.
        if _parses_as_canonical(source):
            return source

        # 2. Cache hit — no model call.
        cache = _load_cache(cache_path)
        if source in cache:
            return cache[source]

        # 3. Cache miss — resolve via the model.
        c = state["client"]
        if c is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise EmmNormalizeError(
                    "set ANTHROPIC_API_KEY to normalize free-English E-- to "
                    "canonical (no cached canonical form for this source)")
            try:
                import anthropic  # lazy: only needed on a live cache miss
            except ImportError as exc:
                raise EmmNormalizeError(
                    "the 'anthropic' package is required to normalize "
                    "free-English E-- but is not installed. Run: "
                    "pip install -r requirements.txt") from exc
            c = anthropic.Anthropic(api_key=api_key)
            state["client"] = c

        try:
            response = c.messages.create(
                model=model,
                max_tokens=2048,
                temperature=0,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": source}],
            )
        except Exception as exc:  # SDK / transport / auth errors
            name = type(exc).__name__
            if "Authentication" in name or "invalid x-api-key" in str(exc):
                raise EmmNormalizeError(
                    "Anthropic rejected the API key (authentication error) "
                    "while normalizing free-English E--. Check that "
                    "ANTHROPIC_API_KEY is a valid, current key with no extra "
                    f"quotes or whitespace. Original error: {exc}") from exc
            raise EmmNormalizeError(
                f"LLM call failed while normalizing source: "
                f"{name}: {exc}") from exc

        raw = response.content[0].text
        result = _strip_fences(raw)

        # 4. Validate by re-parsing — never accept un-parseable "canonical".
        try:
            parse(tokenize(result))
        except EmmSyntaxError as exc:
            raise EmmNormalizeError(
                "the model's normalization did not parse as canonical E--. "
                f"Parse error: {exc}\n--- model output ---\n{raw}") from exc

        # 5. Cache and return.
        cache[source] = result
        _write_cache(cache_path, cache)
        return result

    return normalize
