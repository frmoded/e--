"""Test matrix for the E-- deterministic core (prompt §5)."""

import os
import subprocess
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from transpiler import transpile  # noqa: E402
from errors import EmmSyntaxError  # noqa: E402


def fake(text):
    """Fake slot resolver: known phrases -> Python literal text."""
    mapping = {
        "the first prime number greater than 5": "7",
        "a calm blue": '"blue"',
    }
    if text in mapping:
        return mapping[text]
    raise AssertionError(f"fake resolver has no mapping for {text!r}")


def t(src):
    return transpile(src, resolve_slot=fake)


class TestLiterals(unittest.TestCase):
    def test_int(self):
        self.assertEqual(t("Set v to 42."), "v = 42")

    def test_float(self):
        self.assertEqual(t("Set v to 3.14."), "v = 3.14")

    def test_negative_int(self):
        self.assertEqual(t("Set v to -1."), "v = -1")

    def test_string(self):
        self.assertEqual(t('Set v to "hi".'), 'v = "hi"')

    def test_true(self):
        self.assertEqual(t("Set v to True."), "v = True")

    def test_false(self):
        self.assertEqual(t("Set v to False."), "v = False")

    def test_nothing(self):
        self.assertEqual(t("Set v to Nothing."), "v = None")


class TestCollections(unittest.TestCase):
    def test_list(self):
        self.assertEqual(t("Set v to <1, 2, 3>."), "v = [1, 2, 3]")

    def test_empty_list(self):
        self.assertEqual(t("Set v to <>."), "v = []")

    def test_dict(self):
        self.assertEqual(t('Set v to {"a": 1}.'), 'v = {"a": 1}')

    def test_empty_dict(self):
        self.assertEqual(t("Set v to {}."), "v = {}")


class TestVariables(unittest.TestCase):
    def test_variable_rhs(self):
        self.assertEqual(t("Set v to x."), "v = x")

    def test_assign_from_variable(self):
        self.assertEqual(t("Set total to count."), "total = count")


class TestCalls(unittest.TestCase):
    def test_call_discarded(self):
        self.assertEqual(t("Do [[print]](x)."), "print(x)")

    def test_call_kept(self):
        self.assertEqual(t("Set v to [[f]](3, 2)."), "v = f(3, 2)")

    def test_call_nested(self):
        self.assertEqual(
            t("Set v to [[f]]([[g]](3), 2)."), "v = f(g(3), 2)")


class TestKeywordArguments(unittest.TestCase):
    def test_single_keyword(self):
        self.assertEqual(t("Set v to [[f]](x=1)."), "v = f(x=1)")

    def test_mixed_positional_then_keyword(self):
        self.assertEqual(t("Set v to [[f]](a, x=1)."), "v = f(a, x=1)")

    def test_multiple_keywords(self):
        self.assertEqual(
            t('Set c to [[major_chord]](root="C", inversion=2).'),
            'c = major_chord(root="C", inversion=2)')

    def test_keyword_value_nested_call(self):
        self.assertEqual(
            t("Set s to [[compose]](drums=[[shuffle]]())."),
            "s = compose(drums=shuffle())")

    def test_keyword_value_infix_chain(self):
        self.assertEqual(
            t("Set v to [[f]](n=a plus b)."), "v = f(n=a + b)")

    def test_keyword_value_slot(self):
        self.assertEqual(
            t("Set v to [[plot]](color={{a calm blue}})."),
            'v = plot(color="blue")')

    def test_do_with_keywords(self):
        self.assertEqual(
            t("Do [[connect]](host, port=8080)."),
            "connect(host, port=8080)")

    def test_positional_after_keyword_raises(self):
        with self.assertRaises(EmmSyntaxError):
            t("Set v to [[f]](x=1, y).")

    def test_bare_variable_positional_unaffected(self):
        # A bare variable positional has no following '=', so the new lookahead
        # leaves it a positional arg.
        self.assertEqual(t("Set v to [[f]](x)."), "v = f(x)")


class TestOperators(unittest.TestCase):
    def test_single_op_chain(self):
        self.assertEqual(
            t("Set v to a plus b plus c."), "v = a + b + c")

    def test_mixed_op_rejected(self):
        with self.assertRaises(EmmSyntaxError):
            t("Set v to 2 plus 3 times 4.")

    def test_grouping(self):
        self.assertEqual(
            t("Set v to (2 plus 3) times 4."), "v = (2 + 3) * 4")


class TestComparisonHeader(unittest.TestCase):
    def test_if_greater_than(self):
        src = "If a is greater than b:\n    Do [[print]](a).\n"
        self.assertEqual(t(src), "if a > b:\n    print(a)")


class TestNot(unittest.TestCase):
    def test_not_simple(self):
        self.assertEqual(t("Set v to not a."), "v = not a")

    def test_grouped_not_equals(self):
        self.assertEqual(
            t("Set v to (not a) equals b."), "v = (not a) == b")

    def test_ungrouped_not_with_op_rejected(self):
        with self.assertRaises(EmmSyntaxError):
            t("Set v to not a equals b.")


class TestMembership(unittest.TestCase):
    def test_is_in(self):
        src = "If x is in items:\n    Do [[print]](x).\n"
        self.assertEqual(t(src), "if x in items:\n    print(x)")

    def test_is_not_in(self):
        src = "If x is not in items:\n    Do [[print]](x).\n"
        self.assertEqual(t(src), "if x not in items:\n    print(x)")


class TestLoops(unittest.TestCase):
    def test_for_each(self):
        src = "For each y in items:\n    Do [[print]](y).\n"
        self.assertEqual(t(src), "for y in items:\n    print(y)")

    def test_while_giveback_in_define(self):
        src = (
            "Define [[count_down]] taking n:\n"
            "    While n is greater than 0:\n"
            "        Set n to n minus 1.\n"
            "    Give back n.\n"
        )
        expected = (
            "def count_down(n):\n"
            "    while n > 0:\n"
            "        n = n - 1\n"
            "    return n"
        )
        self.assertEqual(t(src), expected)


class TestDefine(unittest.TestCase):
    def test_taking_nothing(self):
        src = 'Define [[banner]] taking nothing:\n    Do [[print]]("===").\n'
        self.assertEqual(t(src), 'def banner():\n    print("===")')

    def test_default_param(self):
        src = (
            'Define [[greet]] taking name defaulting to "world":\n'
            "    Do [[print]](name).\n"
        )
        self.assertEqual(t(src), 'def greet(name="world"):\n    print(name)')

    def test_nested_blocks(self):
        src = (
            "Define [[f]] taking items:\n"
            "    For each x in items:\n"
            "        If x is greater than 0:\n"
            "            Do [[print]](x).\n"
        )
        expected = (
            "def f(items):\n"
            "    for x in items:\n"
            "        if x > 0:\n"
            "            print(x)"
        )
        self.assertEqual(t(src), expected)


class TestConditionals(unittest.TestCase):
    def test_if_else(self):
        src = (
            "If a is greater than b:\n"
            "    Do [[print]](a).\n"
            "Otherwise:\n"
            "    Do [[print]](b).\n"
        )
        expected = (
            "if a > b:\n"
            "    print(a)\n"
            "else:\n"
            "    print(b)"
        )
        self.assertEqual(t(src), expected)

    def test_if_elif_else(self):
        src = (
            "If a is greater than b:\n"
            "    Do [[print]](a).\n"
            "Otherwise if a is less than b:\n"
            "    Do [[print]](b).\n"
            "Otherwise:\n"
            "    Do [[print]](c).\n"
        )
        expected = (
            "if a > b:\n"
            "    print(a)\n"
            "elif a < b:\n"
            "    print(b)\n"
            "else:\n"
            "    print(c)"
        )
        self.assertEqual(t(src), expected)

    def test_multiple_elif_no_else(self):
        src = (
            "If x is at least 90:\n"
            "    Set g to \"A\".\n"
            "Otherwise if x is at least 80:\n"
            "    Set g to \"B\".\n"
            "Otherwise if x is at least 70:\n"
            "    Set g to \"C\".\n"
        )
        expected = (
            "if x >= 90:\n"
            "    g = \"A\"\n"
            "elif x >= 80:\n"
            "    g = \"B\"\n"
            "elif x >= 70:\n"
            "    g = \"C\""
        )
        self.assertEqual(t(src), expected)

    def test_spec_grade_example(self):
        src = (
            "If score is at least 90:\n"
            "    Set grade to \"A\".\n"
            "Otherwise if score is at least 80:\n"
            "    Set grade to \"B\".\n"
            "Otherwise if score is at least 70:\n"
            "    Set grade to \"C\".\n"
            "Otherwise:\n"
            "    Set grade to \"F\".\n"
        )
        expected = (
            "if score >= 90:\n"
            "    grade = \"A\"\n"
            "elif score >= 80:\n"
            "    grade = \"B\"\n"
            "elif score >= 70:\n"
            "    grade = \"C\"\n"
            "else:\n"
            "    grade = \"F\""
        )
        self.assertEqual(t(src), expected)

    def test_if_else_nested_in_for_each(self):
        src = (
            "For each n in items:\n"
            "    If n is greater than 0:\n"
            "        Do [[print]](n).\n"
            "    Otherwise:\n"
            "        Do [[print]](0).\n"
        )
        expected = (
            "for n in items:\n"
            "    if n > 0:\n"
            "        print(n)\n"
            "    else:\n"
            "        print(0)"
        )
        self.assertEqual(t(src), expected)

    def test_dangling_otherwise(self):
        with self.assertRaises(EmmSyntaxError):
            t("Otherwise:\n    Do [[print]](x).\n")

    def test_dangling_otherwise_if(self):
        with self.assertRaises(EmmSyntaxError):
            t("Otherwise if a equals b:\n    Do [[print]](x).\n")

    def test_otherwise_then_otherwise_if_rejected(self):
        src = (
            "If a equals b:\n"
            "    Do [[print]](a).\n"
            "Otherwise:\n"
            "    Do [[print]](b).\n"
            "Otherwise if a equals c:\n"
            "    Do [[print]](c).\n"
        )
        with self.assertRaises(EmmSyntaxError):
            t(src)

    def test_two_otherwise_rejected(self):
        src = (
            "If a equals b:\n"
            "    Do [[print]](a).\n"
            "Otherwise:\n"
            "    Do [[print]](b).\n"
            "Otherwise:\n"
            "    Do [[print]](c).\n"
        )
        with self.assertRaises(EmmSyntaxError):
            t(src)

    def test_plain_if_regression(self):
        src = "If a is greater than b:\n    Do [[print]](a).\n"
        self.assertEqual(t(src), "if a > b:\n    print(a)")


class TestLlmSlots(unittest.TestCase):
    def test_slot_via_fake(self):
        src = ("Set v to [[fibonacci]]"
               "( {{the first prime number greater than 5}} ).")
        self.assertEqual(t(src), "v = fibonacci(7)")

    def test_default_resolver_raises(self):
        with self.assertRaises(NotImplementedError):
            transpile("Set v to {{anything}}.")


DESCRIBE_PY = (
    "def describe(n):\n"
    "    if n > 10:\n"
    "        return \"big\"\n"
    "    return \"small\"\n"
    "for n in [3, 42, 7]:\n"
    "    print(describe(n))"
)

_CLI = os.path.join(_REPO_ROOT, "src", "transpiler.py")
_DESCRIBE_EMM = os.path.join(_REPO_ROOT, "examples", "describe.emm")


class TestCliRunner(unittest.TestCase):
    def test_transpile_describe_example(self):
        with open(_DESCRIBE_EMM, "r", encoding="utf-8") as fh:
            src = fh.read()
        self.assertEqual(t(src).strip(), DESCRIBE_PY.strip())

    def test_cli_transpile_stdout(self):
        try:
            proc = subprocess.run(
                [sys.executable, _CLI, _DESCRIBE_EMM],
                capture_output=True, text=True, cwd=_REPO_ROOT)
        except OSError as exc:
            self.skipTest(f"cannot spawn subprocess: {exc}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), DESCRIBE_PY.strip())

    def test_cli_run_executes(self):
        try:
            proc = subprocess.run(
                [sys.executable, _CLI, _DESCRIBE_EMM, "--run"],
                capture_output=True, text=True, cwd=_REPO_ROOT)
        except OSError as exc:
            self.skipTest(f"cannot spawn subprocess: {exc}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "small\nbig\nsmall\n")

    def test_cli_missing_file(self):
        try:
            proc = subprocess.run(
                [sys.executable, _CLI, "does/not/exist.emm"],
                capture_output=True, text=True, cwd=_REPO_ROOT)
        except OSError as exc:
            self.skipTest(f"cannot spawn subprocess: {exc}")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error", proc.stderr.lower())
        self.assertNotIn("Traceback", proc.stderr)

    def test_cli_run_show_prints_code_then_output(self):
        try:
            proc = subprocess.run(
                [sys.executable, _CLI, _DESCRIBE_EMM, "--run", "--show"],
                capture_output=True, text=True, cwd=_REPO_ROOT)
        except OSError as exc:
            self.skipTest(f"cannot spawn subprocess: {exc}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertIn("def describe(n):", out)
        self.assertIn("# --- output ---", out)
        # Generated Python appears before the program output.
        self.assertLess(
            out.index("def describe(n):"), out.index("# --- output ---"))
        tail = out.split("# --- output ---", 1)[1]
        self.assertEqual(tail.strip().splitlines(), ["small", "big", "small"])

    def test_cli_show_alone_does_not_run(self):
        try:
            proc = subprocess.run(
                [sys.executable, _CLI, _DESCRIBE_EMM, "--show"],
                capture_output=True, text=True, cwd=_REPO_ROOT)
        except OSError as exc:
            self.skipTest(f"cannot spawn subprocess: {exc}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # No --run: output is exactly the generated Python, nothing executed.
        self.assertEqual(proc.stdout.strip(), DESCRIBE_PY.strip())
        self.assertNotIn("# --- output ---", proc.stdout)


if __name__ == "__main__":
    unittest.main()
