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
from errors import EmmNormalizeError  # noqa: E402

# A free-English source that the deterministic parser will NOT accept.
ENGLISH_SRC = (
    "Define a function called describe that takes a number n. If n is greater "
    "than ten, give back \"big\". Otherwise give back \"small\". Then for each "
    "n in the list 3, 42 and 7, print describe of n.\n"
)

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
    """Mimics client.messages.create(...).content[0].text"""

    def __init__(self, text):
        self._text = text
        self.called = False
        self.messages = self

    def create(self, **kwargs):
        self.called = True
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
        with open(self.cache_path, "r", encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk[ENGLISH_SRC], CANONICAL_DESCRIBE)

    def test_cache_hit_no_call(self):
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump({ENGLISH_SRC: CANONICAL_DESCRIBE}, fh)
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


if __name__ == "__main__":
    unittest.main()
