"""Tests for the {{ }} slot resolver — NO real API calls (fake client +
temp cache paths only)."""

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from resolver import make_anthropic_resolver  # noqa: E402
from transpiler import transpile  # noqa: E402
from errors import EmmResolveError  # noqa: E402

PRIMES_PHRASE = "the first five prime numbers, as a Python list"


class FakeClient:
    """Mimics the SDK call site: client.messages.create(...).content[0].text"""

    def __init__(self, text):
        self._text = text
        self.called = False
        self.messages = self

    def create(self, **kwargs):
        self.called = True
        return SimpleNamespace(
            content=[SimpleNamespace(text=self._text)])


class RaisingClient:
    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        raise AssertionError("client must not be called on a cache hit")


class _FakeAuthenticationError(Exception):
    """Stands in for anthropic.AuthenticationError (matched by class name)."""

    def __init__(self):
        super().__init__("Error code: 401 - invalid x-api-key")


class AuthErrorClient:
    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        raise _FakeAuthenticationError()


class GenericApiErrorClient:
    def __init__(self):
        self.messages = self

    def create(self, **kwargs):
        raise RuntimeError("connection reset")


class TestResolver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = os.path.join(self.tmp.name, ".emm_cache.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_cache(self, obj):
        with open(self.cache_path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    def test_cache_hit_no_client_call(self):
        self._write_cache({PRIMES_PHRASE: "[2, 3, 5, 7, 11]"})
        client = RaisingClient()
        resolve = make_anthropic_resolver(
            cache_path=self.cache_path, client=client)
        self.assertEqual(resolve(PRIMES_PHRASE), "[2, 3, 5, 7, 11]")

    def test_cache_miss_resolves_and_writes(self):
        client = FakeClient("[2, 3, 5, 7, 11]")
        resolve = make_anthropic_resolver(
            cache_path=self.cache_path, client=client)
        self.assertEqual(resolve(PRIMES_PHRASE), "[2, 3, 5, 7, 11]")
        self.assertTrue(client.called)
        with open(self.cache_path, "r", encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk[PRIMES_PHRASE], "[2, 3, 5, 7, 11]")

    def test_invalid_model_output_raises(self):
        client = FakeClient("this is not python !!!")
        resolve = make_anthropic_resolver(
            cache_path=self.cache_path, client=client)
        with self.assertRaises(EmmResolveError):
            resolve(PRIMES_PHRASE)

    def test_code_fence_stripping(self):
        client = FakeClient("```python\n7\n```")
        resolve = make_anthropic_resolver(
            cache_path=self.cache_path, client=client)
        self.assertEqual(resolve("a prime"), "7")

    def test_missing_key_raises_no_network(self):
        # No client, no API key, cache miss -> EmmResolveError before any
        # client construction or network.
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        resolve = make_anthropic_resolver(cache_path=self.cache_path)
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EmmResolveError) as ctx:
                resolve(PRIMES_PHRASE)
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_auth_error_wrapped(self):
        resolve = make_anthropic_resolver(
            cache_path=self.cache_path, client=AuthErrorClient())
        with self.assertRaises(EmmResolveError) as ctx:
            resolve(PRIMES_PHRASE)
        self.assertIn("authentication", str(ctx.exception).lower())

    def test_generic_api_error_wrapped(self):
        resolve = make_anthropic_resolver(
            cache_path=self.cache_path, client=GenericApiErrorClient())
        with self.assertRaises(EmmResolveError) as ctx:
            resolve(PRIMES_PHRASE)
        self.assertIn("connection reset", str(ctx.exception))

    def test_end_to_end_transpile_with_cache(self):
        self._write_cache({PRIMES_PHRASE: "[2, 3, 5, 7, 11]"})
        resolve = make_anthropic_resolver(
            cache_path=self.cache_path, client=RaisingClient())
        with open(os.path.join(_REPO_ROOT, "examples", "primes.emm"),
                  "r", encoding="utf-8") as fh:
            src = fh.read()
        expected = "for p in [2, 3, 5, 7, 11]:\n    print(p)"
        self.assertEqual(transpile(src, resolve_slot=resolve), expected)


if __name__ == "__main__":
    unittest.main()
