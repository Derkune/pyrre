from pyrre.types import LexerError, ParserError, CallStack
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import advance_step


if __name__ == "__main__":
    with open("testprogram.rre", "r", encoding="utf-8") as _f:
        lexed = lex(_f.read())
        assert not isinstance(lexed, LexerError)
        parsed = parse(lexed)
        assert not isinstance(parsed, ParserError)
        stack = CallStack(parsed)
        history = []
        for _ in range(1000):
            history.append(stack)
            stack = advance_step(stack)
        pass
