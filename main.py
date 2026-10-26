from pyrre.types import RRE_INT
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import Runtime
from pyrre.dumping import dump_history, prettify_chars


if __name__ == "__main__":
    with open("triangle.rre", "r", encoding="utf-8") as _f:
        lexed = lex(_f.read())
        parsed = parse(lexed)
        pass

        runtime = Runtime(parsed, [RRE_INT(20)])
        try:
            result = runtime.run_program()
            print(prettify_chars(result))
        finally:
            with open("dump.txt", "w") as _f:
                _f.write(dump_history(runtime.history, parsed))
