from pyrre.types import ProgramStack, RRE_LIST, RRE_INT
from pyrre.lexer import lex
from pyrre.parser import parse
from pyrre.runtime import execute_step


CASE_1: str = """
func main()
    var1 = +(1, +(1, 1))
    var2 = -("A", [])
    var3 = otherfunc(var1, var2)
    return thirdfunc(var1, var2, var3)
endfunc

func otherfunc(arg1, arg2)
    return >(arg1, arg2)
endfunc

func thirdfunc(arg1, arg2, arg3)
    return +(+(arg1, arg2), arg3)
endfunc
"""


def test_integration_1() -> None:
    lexed = lex(CASE_1)
    parsed = parse(lexed)

    stack = ProgramStack(parsed, [])
    for _ in range(1000):
        if stack.final_value is not None:
            assert stack.final_value == RRE_LIST((RRE_INT(3), RRE_INT(65), RRE_INT(0)))
            return
        stack = execute_step(stack)

    assert False
