from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import execute_step
from pyrre.types import (
    FunctionStackFrame,
    ProgramStack,
    RRE_ERROR,
    RRE_INT,
)
from rre_testutil import apply_memoize_modifier, run_program

import pytest


@pytest.mark.parametrize("memoize", [False, True])
def test_positive_countdown_succeeds(memoize: bool) -> None:
    code = """
    func rec(n)!
        done = >(0, n)
        smaller = -(n, 1)
        return ?(done, rec(smaller))
    endfunc

    func main()
        return rec(3)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_negative_countdown_toward_zero_succeeds(memoize: bool) -> None:
    code = """
    func rec(n)!
        done = >(n, 0)
        closer = +(n, 1)
        return ?(done, rec(closer))
    endfunc

    func main(n)
        return rec(n)
    endfunc
    """
    assert run_program(code, inputs=[RRE_INT(-3)], memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_growing_argument_fails(memoize: bool) -> None:
    code = """
    func rec(n)!
        bigger = +(n, 1)
        return rec(bigger)
    endfunc

    func main()
        return rec(1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("wellfoundedness")


@pytest.mark.parametrize("memoize", [False, True])
def test_equal_magnitude_fails(memoize: bool) -> None:
    code = """
    func rec(n)!
        negated = -(0, n)
        return rec(negated)
    endfunc

    func main()
        return rec(3)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("wellfoundedness")


@pytest.mark.parametrize("memoize", [False, True])
def test_zero_argument_self_call_fails(memoize: bool) -> None:
    code = """
    func rec()!
        return rec()
    endfunc

    func main()
        return rec()
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("wellfoundedness")


@pytest.mark.parametrize("memoize", [False, True])
def test_mutual_recursion_decreasing_succeeds(memoize: bool) -> None:
    code = """
    func even(n)!
        done = >(0, n)
        smaller = -(n, 1)
        return ?(done, odd(smaller))
    endfunc

    func odd(n)!
        smaller = -(n, 1)
        return even(smaller)
    endfunc

    func main()
        return even(2)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_mutual_recursion_equal_args_fails(memoize: bool) -> None:
    code = """
    func even(n)!
        return odd(n)
    endfunc

    func odd(n)!
        return even(n)
    endfunc

    func main()
        return even(2)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("wellfoundedness")


@pytest.mark.parametrize("memoize", [False, True])
def test_main_bang_calling_other_bang_succeeds(memoize: bool) -> None:
    code = """
    func alpha(a)!
        return a
    endfunc

    func main()!
        return alpha(10)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(10)


@pytest.mark.parametrize("memoize", [False, True])
def test_sequential_calls_second_larger_succeeds(memoize: bool) -> None:
    code = """
    func rec(n)!
        return n
    endfunc

    func main()
        first = rec(1)
        return rec(3)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(3)


@pytest.mark.parametrize("memoize", [False, True])
def test_lexicographic_later_component_may_shrink(memoize: bool) -> None:
    code = """
    func pair(a, b)!
        done = >(0, b)
        nextb = -(b, 1)
        return ?(done, pair(a, nextb))
    endfunc

    func main()
        return pair(5, 2)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_equal_argument_tuple_fails(memoize: bool) -> None:
    code = """
    func pair(a, b)!
        return pair(a, b)
    endfunc

    func main()
        return pair(1, 2)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("wellfoundedness")


@pytest.mark.parametrize("memoize", [False, True])
def test_list_argument_shrinks_when_item_removed(memoize: bool) -> None:
    code = """
    func rec(xs)!
            rest = -(xs, 1)
        empty = >(0, -(0, xs))
        return ?(empty, rec(rest))
    endfunc

    func main()
        return rec("AB")
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_tail_wellfounded_countdown_stays_within_depth(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func rec(n)!@
        done = >(0, n)
        smaller = -(n, 1)
        return ?(done, rec(smaller))
    endfunc

    func main()
        return rec(5)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_tail_unchanged_args_errors_instead_of_spinning(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func rec()!@
        return rec()
    endfunc

    func main()
        return rec()
    endfunc
    """
    if memoize:
        code = apply_memoize_modifier(code)
    stack = ProgramStack(parse(lex(code)), [])
    for _ in range(200):
        stack = execute_step(stack)
        func_frames = sum(
            isinstance(frame, FunctionStackFrame) for frame in stack.call_stack
        )
        assert func_frames <= 2
        if stack.final_value is not None:
            assert stack.final_value == RRE_ERROR("wellfoundedness")
            return
    pytest.fail("tail self-call with unchanged arguments did not error")


@pytest.mark.parametrize("memoize", [False, True])
def test_percent_force_while_live_decreasing_succeeds(memoize: bool) -> None:
    code = """
    func rec(n)!%
        done = >(0, n)
        smaller = -(n, 1)
        return ?(done, ?(0, rec(smaller)))
    endfunc

    func main()
        return ?(0, rec(3))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_percent_force_while_live_equal_args_fails(memoize: bool) -> None:
    code = """
    func rec(n)!%
        return ?(0, rec(n))
    endfunc

    func main()
        return ?(0, rec(3))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("wellfoundedness")


@pytest.mark.parametrize("memoize", [False, True])
def test_memo_hit_of_completed_call_is_not_checked(memoize: bool) -> None:
    code = """
    func rec(n)!
        done = >(1, n)
        n1 = -(n, 1)
        left = ?(done, rec(n1))
        right = ?(done, rec(n1))
        return +(left, right)
    endfunc

    func main()
        return rec(3)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(8)
