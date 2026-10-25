from typing import Any

from pyrre.types import (
    ProgramStack,
    RRE_INT,
    RRE_ERROR,
    RRE_LIST,
)
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import execute_step

import pytest

from rre_testutil import apply_memoize_modifier


FIB: str = """
func main(n)
    return fib(n)
endfunc

func fib(n)
    done = >(1, n)
    n1 = -(n, 1)
    n2 = -(n, 2)
    rec = ?(done, +(fib(n1), fib(n2)))
    pick = -(1, done)
    choices = +(+(n, []), rec)
    return -(pick, choices)
endfunc
"""

FIB_MEMO: str = """
func main(n)
    return fib(n)
endfunc

func fib(n)#
    done = >(1, n)
    n1 = -(n, 1)
    n2 = -(n, 2)
    rec = ?(done, +(fib(n1), fib(n2)))
    pick = -(1, done)
    choices = +(+(n, []), rec)
    return -(pick, choices)
endfunc
"""


def run_program(
    code: str,
    *,
    inputs: None | list[Any] = None,
    max_steps: int = 10000,
    allow_timeout: bool = False,
) -> tuple[Any, int]:
    if inputs is None:
        inputs = []
    lexed = lex(code)
    parsed = parse(lexed)
    stack = ProgramStack(parsed, inputs)

    steps = 0
    for _ in range(max_steps):
        if stack.final_value is not None:
            return stack.final_value, steps
        stack = execute_step(stack)
        steps += 1

    if allow_timeout:
        return None, steps
    pytest.fail(f"Execution exceeded max steps ({max_steps}) without returning.")


def test_apply_memoize_modifier_skips_existing_hash() -> None:
    code = "func alpha(a, b)#!\n    return a\nendfunc\n"
    assert apply_memoize_modifier(code) == code


def test_fibonacci_matches_without_memo() -> None:
    inputs = [RRE_INT(8)]
    plain, plain_steps = run_program(FIB, inputs=inputs)
    memoized, memo_steps = run_program(FIB_MEMO, inputs=inputs)
    assert plain == memoized == RRE_INT(21)
    assert memo_steps < plain_steps


def test_fibonacci_large_needs_memo() -> None:
    inputs = [RRE_INT(10)]
    timed_out, _timeout_steps = run_program(
        FIB, inputs=inputs, max_steps=600, allow_timeout=True
    )
    assert timed_out is None
    result, _steps = run_program(FIB_MEMO, inputs=inputs, max_steps=600)
    assert result == RRE_INT(55)


def test_different_arguments_are_separate_entries() -> None:
    code = """
    func main()
        return +(add1(1), add1(2))
    endfunc

    func add1(n)#
        return +(n, 1)
    endfunc
    """
    result, _steps = run_program(code)
    assert result == RRE_INT(5)


def test_same_arguments_on_different_functions_do_not_share() -> None:
    code = """
    func main()
        return +(alpha(1), beta(1))
    endfunc

    func alpha(n)#
        return +(n, 1)
    endfunc

    func beta(n)#
        return +(n, 2)
    endfunc
    """
    result, _steps = run_program(code)
    assert result == RRE_INT(5)


def test_list_arguments_use_structural_equality() -> None:
    code = """
    func main()
        a = ident("A")
        b = ident("A")
        return +(a, b)
    endfunc

    func ident(x)#
        return x
    endfunc
    """
    result, _steps = run_program(code)
    expected = RRE_LIST.create(
        (RRE_INT(65), RRE_LIST.create((RRE_INT(65),)))
    )
    assert result == expected


def test_thunk_arguments_use_structural_equality() -> None:
    code = """
    func main()
        t1 = lazy(1)
        t2 = lazy(1)
        return +(count(t1), count(t2))
    endfunc

    func lazy(n)%
        return n
    endfunc

    func count(x)#
        return 1
    endfunc
    """
    result, _steps = run_program(code)
    assert result == RRE_INT(2)


def test_error_result_is_reused() -> None:
    once = """
    func main()
        return boom(1)
    endfunc

    func boom(n)#
        return ~("nope")
    endfunc
    """
    twice = """
    func main()
        a = boom(1)
        return boom(1)
    endfunc

    func boom(n)#
        return ~("nope")
    endfunc
    """
    one_result, one_steps = run_program(once)
    two_result, two_steps = run_program(twice)
    assert one_result == two_result == RRE_ERROR("nope")
    assert two_steps < one_steps * 2


def test_in_flight_same_arguments_still_hit_recursion_depth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func main()
        return rec(1)
    endfunc

    func rec(n)#
        return rec(n)
    endfunc
    """
    result, _steps = run_program(code)
    assert result == RRE_ERROR("recursion depth")


def test_percent_and_hash_still_returns_thunk() -> None:
    code = """
    func main()
        return -(0, wrap(5))
    endfunc

    func wrap(n)#%
        return n
    endfunc
    """
    result, _steps = run_program(code)
    assert result == RRE_INT(5)


def test_percent_and_hash_second_force_skips_body() -> None:
    code = """
    func main()
        t1 = wrap(8)
        t2 = wrap(8)
        a = ?(0, t1)
        b = ?(0, t2)
        return +(a, b)
    endfunc

    func wrap(n)#%
        return fib(n)
    endfunc

    func fib(n)
        done = >(1, n)
        n1 = -(n, 1)
        n2 = -(n, 2)
        rec = ?(done, +(fib(n1), fib(n2)))
        pick = -(1, done)
        choices = +(+(n, []), rec)
        return -(pick, choices)
    endfunc
    """
    without_hash = code.replace("func wrap(n)#%", "func wrap(n)%")
    memoized, memo_steps = run_program(code)
    plain, plain_steps = run_program(without_hash)
    assert memoized == plain == RRE_INT(42)
    assert memo_steps < plain_steps
