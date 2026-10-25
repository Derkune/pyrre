from pyrre.types import ProgramStack
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import execute_step
from pyrre.dumping import dump_history


if __name__ == "__main__":
    with open("simplechoise.rre", "r", encoding="utf-8") as _f:
        lexed = lex(_f.read())
        parsed = parse(lexed)
        pass
        stack: ProgramStack = ProgramStack(parsed, [])
        history: list[ProgramStack] = [stack]
        for _ in range(1000):
            with open("dump.txt", "w") as _f:
                _f.write(dump_history(history, parsed))

            stack = execute_step(stack)
            history.append(stack)
        pass
