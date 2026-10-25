from typing import Any

from pyrre.types import (
    ProgramStack,
    RRE_INT,
    RRE_LIST,
)
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import execute_step
from pyrre.dumping import dump_history

import pytest


def run_program(
    code: str,
    *,
    inputs: None | list[Any] = None,
    max_steps: int = 1000,
    to_dump_history: bool = False,
) -> Any:
    if inputs is None:
        inputs = []
    lexed = lex(code)
    parsed = parse(lexed)
    stack = ProgramStack(parsed, inputs)

    history = []
    for _ in range(max_steps):
        history.append(stack)
        if stack.final_value is not None:
            if to_dump_history:
                with open("dump.txt", "w") as _f:
                    _f.write(dump_history(history, parsed))

            return stack.final_value
        stack = execute_step(stack)

    if to_dump_history:
        with open("dump.txt", "w") as _f:
            _f.write(dump_history(history))

    pytest.fail(f"Execution exceeded max steps ({max_steps}) without returning.")


TRIANGULAR: str = """
func main(n)
    return tri(n, 0)
endfunc

func tri(n, acc)%
    done = >(0, n)
    index = -(1, done)
    base = +(acc, [])
    smaller = -(n, 1)
    summed = +(acc, n)
    recur = tri(smaller, summed)
    choices = +(base, recur)
    return -(index, choices)
endfunc
"""


@pytest.mark.parametrize(
    "n, expected",
    [
        (1, 1),
        (5, 15),
        (10, 55),
    ],
)
def test_triangular_number(n: int, expected: int) -> None:
    result = run_program(
        TRIANGULAR,
        inputs=[RRE_INT(n)],
        max_steps=10000,
        to_dump_history=False,
    )
    assert result == RRE_INT(expected)


TRIANGULAR_CHOICE: str = """
func main(n)
    raw = tri(n)
    return -(raw, 1)
endfunc

func tri(n)
    done = >(0, n)
    smaller = -(n, 1)
    rest = ?(done, tri(smaller))
    return +(n, rest)
endfunc
"""


@pytest.mark.parametrize(
    "n, expected",
    [
        (0, 0),
        (1, 1),
        (5, 15),
        (10, 55),
    ],
)
def test_triangular_number_choice(n: int, expected: int) -> None:
    result = run_program(
        TRIANGULAR_CHOICE,
        inputs=[RRE_INT(n)],
        max_steps=10000,
        to_dump_history=False,
    )
    assert result == RRE_INT(expected)


REVERSE: str = """
func main(items)
    return rev(items, [])
endfunc

func rev(items, acc)
    empty = >([], items)
    index = -(1, empty)
    base = +([], acc)
    recur = ?(
        empty, 
        rev(
            -(items, 0), 
            +(-(0, items), acc)
        )
    )
    choices = +(base, recur)
    return -(index, choices)
endfunc
"""


def _int_list(values: list[int]) -> RRE_LIST:
    return RRE_LIST(tuple(RRE_INT(v) for v in values))


@pytest.mark.parametrize(
    "values, expected",
    [
        ([], []),
        ([1], [1]),
        ([1, 2, 3], [3, 2, 1]),
        ([4, -2, 0, 7], [7, 0, -2, 4]),
    ],
)
def test_reverse_list(values: list[int], expected: list[int]) -> None:
    result = run_program(
        REVERSE,
        inputs=[_int_list(values)],
        max_steps=10000,
        to_dump_history=False,
    )
    assert result == _int_list(expected)


MULTIPLY: str = """
func main(a, b)
    nonneg = >(b, 0)
    pos = times(a, b)
    neg = -(0, times(a, -(0, b)))
    pick = -(1, nonneg)
    choices = +(+(pos, []), neg)
    return -(pick, choices)
endfunc

func times(a, count)
    done = >(0, count)
    smaller = -(count, 1)
    rest = ?(done, +(a, times(a, smaller)))
    return -(rest, done)
endfunc
"""


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (0, 0, 0),
        (0, 5, 0),
        (5, 0, 0),
        (0, -5, 0),
        (-2, 0, 0),
        (1, 7, 7),
        (7, 1, 7),
        (3, 4, 12),
        (6, 7, 42),
        (-3, 4, -12),
        (3, -4, -12),
        (-3, -4, 12),
        (-1, -1, 1),
    ],
)
def test_multiply(a: int, b: int, expected: int) -> None:
    result = run_program(
        MULTIPLY,
        inputs=[RRE_INT(a), RRE_INT(b)],
        max_steps=10000,
        to_dump_history=False,
    )
    assert result == RRE_INT(expected)
