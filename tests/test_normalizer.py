"""Tests for the Phase 1 normalizer (free English -> canonical E--).

NO real API calls: fake client + temp cache paths only.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from normalizer import make_normalizer  # noqa: E402
from transpiler import transpile  # noqa: E402
from parser import is_canonical_statement_line  # noqa: E402
from errors import EmmNormalizeError  # noqa: E402

# A free-English source that the deterministic parser will NOT accept.
ENGLISH_SRC = (
    "Define a function called describe that takes a number n. If n is greater "
    "than ten, give back \"big\". Otherwise give back \"small\". Then for each "
    "n in the list 3, 42 and 7, print describe of n.\n"
)
# Per-region cache key for ENGLISH_SRC: all-English -> a single region whose key
# is its lines joined (the trailing newline is dropped by splitlines()).
ENGLISH_REGION_KEY = "\n".join(ENGLISH_SRC.splitlines())

# The canonical form a (fake) model would return for ENGLISH_SRC — equivalent
# to examples/describe.emm.
CANONICAL_DESCRIBE = (
    "Define [[describe]] taking n:\n"
    "    If n is greater than 10:\n"
    "        Give back \"big\".\n"
    "    Give back \"small\".\n"
    "\n"
    "For each n in <3, 42, 7>:\n"
    "    Do [[print]]([[describe]](n))."
)

EXPECTED_PYTHON = (
    "def describe(n):\n"
    "    if n > 10:\n"
    "        return \"big\"\n"
    "    return \"small\"\n"
    "for n in [3, 42, 7]:\n"
    "    print(describe(n))"
)


class FakeClient:
    """Mimics client.messages.create(...).content[0].text and counts calls."""

    def __init__(self, text):
        self._text = text
        self.calls = 0
        self.messages = self

    @property
    def called(self):
        return self.calls > 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


class RaisingClient:
    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        raise AssertionError("client must not be called on this path")


class TestNormalizer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = os.path.join(self.tmp.name, ".emm_norm_cache.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _read_describe_emm(self):
        with open(os.path.join(_REPO_ROOT, "examples", "describe.emm"),
                  "r", encoding="utf-8") as fh:
            return fh.read()

    def test_already_canonical_passthrough_no_call(self):
        src = self._read_describe_emm()
        client = RaisingClient()
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        # Returns input unchanged; client never called (detection short-circuit).
        self.assertEqual(normalize(src), src)
        self.assertFalse(os.path.exists(self.cache_path))

    def test_english_normalizes_and_writes_cache(self):
        client = FakeClient(CANONICAL_DESCRIBE)
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        result = normalize(ENGLISH_SRC)
        self.assertEqual(result, CANONICAL_DESCRIBE)
        self.assertTrue(client.called)
        # The returned canonical parses (validated by re-parse inside normalize).
        # Cache is keyed by the region text, not the raw source.
        with open(self.cache_path, "r", encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk[ENGLISH_REGION_KEY], CANONICAL_DESCRIBE)

    def test_cache_hit_no_call(self):
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump({ENGLISH_REGION_KEY: CANONICAL_DESCRIBE}, fh)
        normalize = make_normalizer(
            cache_path=self.cache_path, client=RaisingClient())
        self.assertEqual(normalize(ENGLISH_SRC), CANONICAL_DESCRIBE)

    def test_invalid_model_output_raises(self):
        client = FakeClient("this is still just free English, not canonical")
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        with self.assertRaises(EmmNormalizeError):
            normalize(ENGLISH_SRC)

    def test_missing_key_raises_no_network(self):
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        normalize = make_normalizer(cache_path=self.cache_path)
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EmmNormalizeError) as ctx:
                normalize(ENGLISH_SRC)
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_end_to_end_english_to_python(self):
        normalize = make_normalizer(
            cache_path=self.cache_path, client=FakeClient(CANONICAL_DESCRIBE))
        canonical = normalize(ENGLISH_SRC)
        python_src = transpile(canonical)  # no slots -> default resolver unused
        self.assertEqual(python_src, EXPECTED_PYTHON)

    def test_cli_dual_output_canonical_file(self):
        # Canonical input (no key needed) + --canonical-out writes canonical and
        # produces Python on stdout.
        canonical_in = os.path.join(self.tmp.name, "in.emm")
        with open(canonical_in, "w", encoding="utf-8") as fh:
            fh.write(self._read_describe_emm())
        canon_out = os.path.join(self.tmp.name, "out.em")
        try:
            proc = subprocess.run(
                [sys.executable,
                 os.path.join(_REPO_ROOT, "src", "transpiler.py"),
                 canonical_in, "--canonical-out", canon_out],
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            self.skipTest(f"cannot spawn subprocess: {exc}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.exists(canon_out))
        with open(canon_out, "r", encoding="utf-8") as fh:
            self.assertIn("Define [[describe]] taking n:", fh.read())
        self.assertIn("def describe(n):", proc.stdout)

    # --- per-region behavior ---------------------------------------------

    def test_canonical_lines_preserved_byte_for_byte(self):
        # Canonical Define header + English body line + canonical Give back.
        src = (
            "Define [[describe]] taking n:\n"
            "    make the result equal to 5\n"
            "    Give back result.\n"
        )
        client = FakeClient("Set result to 5.")  # canonical for the English line
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        out = normalize(src)
        out_lines = out.split("\n")
        # The two canonical lines survive identical to the input.
        self.assertEqual(out_lines[0], "Define [[describe]] taking n:")
        self.assertIn("    Give back result.", out_lines)
        # Only the single English region went to the model.
        self.assertEqual(client.calls, 1)
        # Re-indented to the English line's indent (4 spaces).
        self.assertIn("    Set result to 5.", out_lines)

    def test_per_region_cache_only_misses_call(self):
        # Two English regions separated by a canonical line; one is pre-cached.
        src = (
            "make x equal to 1\n"
            "Do [[print]](x).\n"
            "make y equal to 2\n"
        )
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump({"make x equal to 1": "Set x to 1."}, fh)
        client = FakeClient("Set y to 2.")
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        out = normalize(src)
        self.assertEqual(client.calls, 1)  # only region B missed
        self.assertEqual(
            out, "Set x to 1.\nDo [[print]](x).\nSet y to 2.")

    def test_reindentation_matches_english_indent(self):
        src = (
            "Define [[f]] taking n:\n"
            "    look up n in the table\n"
        )
        client = FakeClient("Do [[g]](n).")  # level-0 canonical
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        out_lines = normalize(src).split("\n")
        english_indent = "    "  # the English line's leading whitespace
        normalized = [ln for ln in out_lines if ln.strip() == "Do [[g]](n)."][0]
        leading = normalized[:len(normalized) - len(normalized.lstrip(" "))]
        self.assertEqual(leading, english_indent)

    def test_stitched_validation_failure_raises(self):
        src = (
            "Do [[print]](1).\n"
            "make a thing happen\n"
        )
        client = FakeClient("this is not canonical at all")
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        with self.assertRaises(EmmNormalizeError):
            normalize(src)

    def test_missing_key_on_mixed_file_no_network(self):
        src = "Do [[print]](1).\nmake a thing happen\n"
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        normalize = make_normalizer(cache_path=self.cache_path)
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EmmNormalizeError) as ctx:
                normalize(src)
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_mixed_file_all_cached_needs_no_key(self):
        src = "Do [[print]](1).\nmake a thing happen\n"
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump({"make a thing happen": "Do [[thing]]()."}, fh)
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        # No client and no key: the cache short-circuits before any client.
        normalize = make_normalizer(cache_path=self.cache_path)
        with mock.patch.dict(os.environ, env, clear=True):
            out = normalize(src)
        self.assertEqual(out, "Do [[print]](1).\nDo [[thing]]().")

    def test_end_to_end_mixed_to_python(self):
        src = (
            "Define [[describe]] taking n:\n"
            "    if n is bigger than ten, give back \"big\"\n"
            "    Give back \"small\".\n"
            "\n"
            "For each n in <3, 42, 7>:\n"
            "    Do [[print]]([[describe]](n)).\n"
        )
        # Fake returns level-0 canonical for the one English region.
        client = FakeClient("If n is greater than 10:\n    Give back \"big\".")
        normalize = make_normalizer(cache_path=self.cache_path, client=client)
        canonical = normalize(src)
        self.assertEqual(transpile(canonical), EXPECTED_PYTHON)

    def test_single_line_detector_true_and_false(self):
        for canonical in (
            "Set x to 1.",
            "Do [[f]](x).",
            "Give back result.",
            "If a is greater than b:",
            "Otherwise if a is less than b:",
            "Otherwise:",
            "While a is less than b:",
            "For each x in xs:",
            "Define [[f]] taking n:",
            "    Give back \"big\".",  # leading indent is stripped
        ):
            self.assertTrue(
                is_canonical_statement_line(canonical), canonical)
        for english in (
            "make a function that adds",
            "print the total",
            "loop over years",
            "if n is bigger than ten, give back big",
            "",
            "Set x to 1. Do [[f]](x).",  # two statements on one line
        ):
            self.assertFalse(
                is_canonical_statement_line(english), english)


if __name__ == "__main__":
    unittest.main()
