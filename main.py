from pyrre.lexer import lex


if __name__ == "__main__":
    with open("testprogram.rre", "r", encoding="utf-8") as _f:
        lexed = lex(_f.read())
        pass
