from pyrre.lexer import lex
from pyrre.parser import parse


if __name__ == "__main__":
    with open("testprogram.rre", "r", encoding="utf-8") as _f:
        lexed = lex(_f.read())
        parsed = parse(lexed)
        pass
