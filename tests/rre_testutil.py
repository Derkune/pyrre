import re
from typing import Any

from pyrre.dumping import dump_history
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import execute_step
from pyrre.types import ProgramStack

import pytest

_FUNC_HEADER = re.compile(
    r"(func\s+[A-Za-z][A-Za-z0-9_]*\s*\([^)]*\))(\s*[!@#%]*)"
)


def apply_memoize_modifier(code: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix, mods = match.group(1), match.group(2)
        if "#" in mods:
            return match.group(0)
        return prefix + mods + "#"

    return _FUNC_HEADER.sub(repl, code)


def run_program(
    code: str,
    *,
    inputs: None | list[Any] = None,
    max_steps: int = 1000,
    to_dump_history: bool = False,
    memoize: bool = False,
) -> Any:
    if memoize:
        code = apply_memoize_modifier(code)
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
