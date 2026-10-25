from typing import Any

from pyrre.types import (
    RRE_INT,
    RRE_LIST,
)
from rre_testutil import run_program

import pytest


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


@pytest.mark.parametrize("memoize", [False, True])
@pytest.mark.parametrize(
    "n, expected",
    [
        (1, 1),
        (5, 15),
        (10, 55),
    ],
)
def test_triangular_number(n: int, expected: int, memoize: bool) -> None:
    result = run_program(
        TRIANGULAR,
        inputs=[RRE_INT(n)],
        max_steps=10000,
        to_dump_history=False,
        memoize=memoize,
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


@pytest.mark.parametrize("memoize", [False, True])
@pytest.mark.parametrize(
    "n, expected",
    [
        (0, 0),
        (1, 1),
        (5, 15),
        (10, 55),
    ],
)
def test_triangular_number_choice(n: int, expected: int, memoize: bool) -> None:
    result = run_program(
        TRIANGULAR_CHOICE,
        inputs=[RRE_INT(n)],
        max_steps=10000,
        to_dump_history=False,
        memoize=memoize,
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
    return RRE_LIST.create(tuple(RRE_INT(v) for v in values))


@pytest.mark.parametrize("memoize", [False, True])
@pytest.mark.parametrize(
    "values, expected",
    [
        ([], []),
        ([1], [1]),
        ([1, 2, 3], [3, 2, 1]),
        ([4, -2, 0, 7], [7, 0, -2, 4]),
    ],
)
def test_reverse_list(values: list[int], expected: list[int], memoize: bool) -> None:
    result = run_program(
        REVERSE,
        inputs=[_int_list(values)],
        max_steps=10000,
        to_dump_history=False,
        memoize=memoize,
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


@pytest.mark.parametrize("memoize", [False, True])
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
def test_multiply(a: int, b: int, expected: int, memoize: bool) -> None:
    result = run_program(
        MULTIPLY,
        inputs=[RRE_INT(a), RRE_INT(b)],
        max_steps=10000,
        to_dump_history=False,
        memoize=memoize,
    )
    assert result == RRE_INT(expected)


CAPS: str = """
func main(items)
    return caps(items)
endfunc

func caps(items)
    empty = >([], items)
    index = -(1, empty)
    base = +([], [])
    recur = ?(
        empty,
        +(
            up(-(0, items)),
            caps(-(items, 0))
        )
    )
    choices = +(base, recur)
    return -(index, choices)
endfunc

func up(n)
    lo = >(n, 97)
    hi = >(122, n)
    islo = >(+(lo, hi), 2)
    upper = -(n, 32)
    pick = -(1, islo)
    choices = +(+(upper, []), n)
    return -(pick, choices)
endfunc
"""


@pytest.mark.parametrize("memoize", [False, True])
@pytest.mark.parametrize(
    "values, expected",
    [
        ([], []),
        ([97], [65]),
        ([122], [90]),
        ([96, 97, 122, 123], [96, 65, 90, 123]),
        ([65, 90, 32, 48, 0, -1], [65, 90, 32, 48, 0, -1]),
        ([ord(c) for c in "PyRRE!"], [ord(c) for c in "PYRRE!"]),
    ],
)
def test_caps(values: list[int], expected: list[int], memoize: bool) -> None:
    result = run_program(
        CAPS,
        inputs=[_int_list(values)],
        max_steps=10000,
        to_dump_history=False,
        memoize=memoize,
    )
    assert result == _int_list(expected)


MODULATE: str = """
func main(mods, data)
    return step(mods, data, [])
endfunc

func step(mods, data, acc)
    empty = >([], mods)
    index = -(1, empty)
    base = +([], acc)
    recur = ?(
        empty,
        step(
            -(mods, 0),
            -(data, 0),
            +(acc, pick(-(0, mods), -(0, data)))
        )
    )
    choices = +(base, recur)
    return -(index, choices)
endfunc

func pick(code, item)
    t0 = keep(item)
    t1 = inc(item)
    t2 = zero(item)
    t3 = blank(item)
    t4 = four(item)
    t5 = wrap(item)
    t6 = nest(item)
    c0 = +([], t0)
    c1 = +(c0, t1)
    c2 = +(c1, t2)
    c3 = +(c2, t3)
    c4 = +(c3, t4)
    c5 = +(c4, t5)
    c6 = +(c5, t6)
    return -(code, c6)
endfunc

func keep(item)%
    return item
endfunc

func inc(item)%
    return +(item, 1)
endfunc

func zero(item)%
    return 0
endfunc

func blank(item)%
    return []
endfunc

func four(item)%
    return "FOUR"
endfunc

func wrap(item)%
    return +(item, [])
endfunc

func nest(item)%
    return +([], +(item, []))
endfunc
"""


def _four() -> RRE_LIST:
    return RRE_LIST.create(tuple(RRE_INT(ord(c)) for c in "FOUR"))


def _modulate_expected(pairs: list[tuple[int, int]]) -> RRE_LIST:
    items: list[Any] = []
    for code, item in pairs:
        if code == 0:
            items.append(RRE_INT(item))
        elif code == 1:
            items.append(RRE_INT(item + 1))
        elif code == 2:
            items.append(RRE_INT(0))
        elif code == 3:
            items.append(RRE_LIST.create(()))
        elif code == 4:
            items.append(_four())
        elif code == 5:
            items.append(RRE_LIST.create((RRE_INT(item),)))
        elif code == 6:
            items.append(RRE_LIST.create((RRE_LIST.create((RRE_INT(item),)),)))
        else:
            raise ValueError(f"unexpected modulator {code}")
    return RRE_LIST.create(tuple(items))


@pytest.mark.parametrize("memoize", [False, True])
@pytest.mark.parametrize(
    "mods, data",
    [
        ([], []),
        ([0], [7]),
        ([1], [-2]),
        ([2], [9]),
        ([3], [4]),
        ([4], [1]),
        ([5], [-3]),
        ([6], [2]),
        ([0, 1, 2, 3, 4, 5, 6], [10, 20, 30, 40, 50, 60, 70]),
        ([1, 5, 0, 6], [-1, 0, 8, 3]),
    ],
)
def test_modulate(mods: list[int], data: list[int], memoize: bool) -> None:
    result = run_program(
        MODULATE,
        inputs=[_int_list(mods), _int_list(data)],
        max_steps=10000,
        to_dump_history=False,
        memoize=memoize,
    )
    assert result == _modulate_expected(list(zip(mods, data)))
