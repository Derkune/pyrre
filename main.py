from pyrre.types import ProgramStack
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import execute_step


if __name__ == "__main__":
    with open("simpleprog.rre", "r", encoding="utf-8") as _f:
        lexed = lex(_f.read())
        parsed = parse(lexed)
        pass
        stack: ProgramStack = ProgramStack(parsed, [])
        history: list[ProgramStack] = [stack]
        for _ in range(1000):
            stack = execute_step(stack)
            history.append(stack)
        pass
