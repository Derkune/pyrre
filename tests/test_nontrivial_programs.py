from typing import Any

from pyrre.types import (
    ProgramStack,
    RRE_INT,
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
    return -(
        -(1, >(0, n)),
        +(+(acc, []), tri(-(n, 1), +(acc, n)))
    )
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
    )
    assert result == RRE_INT(expected)
