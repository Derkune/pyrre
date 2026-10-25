from pyrre.types import (
    RRE_LIST,
    RRE_INT,
    RRE_ERROR,
    RRE_THUNK,
    ParserErrorException,
    LexerErrorException,
    RuntimeErrorException,
    Token,
    TokenType,
    FunctionStackFrame,
    ProgramStack,
)
from pyrre.static_config import MAX_LIST_LENGTH, MAX_LIST_NESTING_DEPTH
from pyrre.parser import parse
from pyrre.lexer import lex
from pyrre.runtime import execute_step
from rre_testutil import run_program, apply_memoize_modifier

import pytest


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


@pytest.mark.parametrize("memoize", [False, True])
def test_integration_1(memoize: bool) -> None:
    result = run_program(CASE_1, memoize=memoize)
    assert result == RRE_LIST.create((RRE_INT(3), RRE_INT(65), RRE_INT(0)))


@pytest.mark.parametrize("memoize", [False, True])
def test_int_arithmetic_basic(memoize: bool) -> None:
    code = """
    func main()
        sum = +(40, 2)
        diff = -(10, 15)
        return +(sum, diff)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(37)


@pytest.mark.parametrize("memoize", [False, True])
def test_int_nested_calls(memoize: bool) -> None:
    code = """
    func main()
        return -(+(10, +(20, 30)), 15)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(45)


@pytest.mark.parametrize("memoize", [False, True])
def test_add_int_to_list_prepend(memoize: bool) -> None:
    code = """
    func main()
        list1 = +(65, [])
        return +(66, list1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_LIST.create(
        (RRE_INT(66), RRE_INT(65))
    )


@pytest.mark.parametrize("memoize", [False, True])
def test_add_list_to_int_append(memoize: bool) -> None:
    code = """
    func main()
        return +("A", 66)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_LIST.create(
        (RRE_INT(65), RRE_INT(66))
    )


@pytest.mark.parametrize("memoize", [False, True])
def test_add_list_to_list_nesting(memoize: bool) -> None:
    code = """
    func main()
        return +("A", "B")
    endfunc
    """
    expected = RRE_LIST.create((RRE_INT(65), RRE_LIST.create((RRE_INT(66),))))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_sub_int_list_retrieval_and_clamping(memoize: bool) -> None:
    code = """
    func main()
        idx0 = -(0, "ABC")
        idx_clamped_high = -(99, "ABC")
        neg_idx = -(0, 5)
        idx_clamped_low = -(neg_idx, "ABC")
        return +(+(+([], idx_clamped_low), idx_clamped_high), idx0)
    endfunc
    """

    expected = RRE_LIST.create((RRE_INT(65), RRE_INT(67), RRE_INT(65)))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_sub_list_int_removal_and_clamping(memoize: bool) -> None:
    code = """
    func main()
        mid_removed = -("ABC", 1)
        clamped_high = -("ABC", 50)
        neg_idx = -(0, 10)
        clamped_low = -("ABC", neg_idx)
        return +(+(+([], mid_removed), clamped_high), clamped_low)
    endfunc
    """
    expected = RRE_LIST.create(
        (
            RRE_LIST.create((RRE_INT(65), RRE_INT(67))),
            RRE_LIST.create((RRE_INT(65), RRE_INT(66))),
            RRE_LIST.create((RRE_INT(66), RRE_INT(67))),
        )
    )
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_sub_list_list_difference(memoize: bool) -> None:
    code = """
    func main()
        rem_one = -("ABACA", "A")
        rem_two = -("ABACA", "AA")
        rem_none = -("ABACA", [])
        return +(+(+([], rem_one), rem_two), rem_none)
    endfunc
    """
    rem_one = RRE_LIST.create((RRE_INT(66), RRE_INT(65), RRE_INT(67), RRE_INT(65)))
    rem_two = RRE_LIST.create((RRE_INT(66), RRE_INT(67), RRE_INT(65)))
    rem_none = RRE_LIST.create(
        (RRE_INT(65), RRE_INT(66), RRE_INT(65), RRE_INT(67), RRE_INT(65))
    )

    expected = RRE_LIST.create((rem_one, rem_two, rem_none))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_comparisons_integers(memoize: bool) -> None:
    code = """
    func main()
        gt = >(5, 3)
        eq = ≥(4, 4)
        lt = >(2, 8)
        return +( +(+([], gt), eq), lt)
    endfunc
    """
    expected = RRE_LIST.create((RRE_INT(1), RRE_INT(1), RRE_INT(0)))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_comparisons_list_and_int(memoize: bool) -> None:
    code = """
    func main()
        list_gt_int = >([], 100)
        int_gt_list = >(100, [])
        return +(+([], list_gt_int), int_gt_list)
    endfunc
    """
    expected = RRE_LIST.create((RRE_INT(1), RRE_INT(0)))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_comparisons_lists(memoize: bool) -> None:
    code = """
    func main()
        shorter = >("A", "AA")
        longer = >("AA", "A")
        same_gt = >("B", "A")
        same_lt = >("A", "B")
        same_eq = >("A", "A")
        return +(+(+(+(+([], shorter), longer), same_gt), same_lt), same_eq)
    endfunc
    """
    expected = RRE_LIST.create(
        (RRE_INT(0), RRE_INT(1), RRE_INT(1), RRE_INT(0), RRE_INT(1))
    )
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_function_modifiers_and_distinct_letters(memoize: bool) -> None:
    code = """
    func main()!@#
        res = alpha(10, 20)
        return beta(res)
    endfunc

    func alpha(a, b)#!
        return +(a, b)
    endfunc

    func beta(v)
        return -(v, 5)
    endfunc
    """
    assert run_program(code, to_dump_history=False, memoize=memoize) == RRE_INT(25)


@pytest.mark.parametrize("memoize", [False, True])
def test_main_with_arguments(memoize: bool) -> None:
    code = """
    func main(x, y)
        return +(x, y)
    endfunc
    """
    inputs = [RRE_INT(12), RRE_INT(18)]
    assert run_program(code, inputs=inputs, memoize=memoize) == RRE_INT(30)


def test_error_function_names_starting_with_same_letter() -> None:
    code = """
    func main()
        return 0
    endfunc

    func more()
        return 1
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def test_error_duplicate_function_name() -> None:
    code = """
    func main()
        return 0
    endfunc

    func main()
        return 1
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def test_error_missing_main_entry_point() -> None:
    code = """
    func entry()
        return 0
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def test_error_parameter_named_underscore() -> None:
    code = """
    func main(_)
        return 0
    endfunc
    """
    with pytest.raises(LexerErrorException):
        run_program(code)


def test_error_binding_named_underscore() -> None:
    code = """
    func main()
        _ = 10
        return 0
    endfunc
    """
    with pytest.raises(LexerErrorException):
        run_program(code)


def test_error_binding_name_collides_with_argument() -> None:
    code = """
    func main(arg1)
        arg1 = 10
        return arg1
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def test_error_duplicate_binding_name() -> None:
    code = """
    func main()
        var1 = 10
        var1 = 20
        return var1
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def test_error_binding_referencing_later_binding() -> None:
    code = """
    func main()
        var1 = +(var2, 1)
        var2 = 5
        return var1
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def test_error_invalid_function_modifier_symbol() -> None:
    # Allowed symbols are only: !@#%
    code = """
    func main()^
        return 0
    endfunc
    """
    with pytest.raises(LexerErrorException):
        run_program(code)


def test_error_invalid_string_character() -> None:
    # ASCII chars must be between 32 and 126 (e.g. newline / tabs are invalid)
    code = 'func main()\n    return "\n"\nendfunc'
    with pytest.raises(ParserErrorException):
        run_program(code)


@pytest.mark.parametrize("memoize", [False, True])
def test_max_int_literal_accepted(memoize: bool) -> None:
    code = """
    func main()
        return 127
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(127)


def test_error_int_literal_above_max() -> None:
    code = """
    func main()
        return 128
    endfunc
    """
    with pytest.raises(LexerErrorException):
        run_program(code)


@pytest.mark.parametrize("memoize", [False, True])
def test_add_clamps_above_max_int(memoize: bool) -> None:
    code = """
    func main()
        return +(127, 1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(127)


@pytest.mark.parametrize("memoize", [False, True])
def test_add_in_range_stays_at_max_int(memoize: bool) -> None:
    code = """
    func main()
        return +(126, 1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(127)


@pytest.mark.parametrize("memoize", [False, True])
def test_add_clamps_below_min_int(memoize: bool) -> None:
    code = """
    func main()
        neg_one = -(0, 1)
        neg_127 = -(0, 127)
        min_int = -(neg_127, 1)
        return +(min_int, neg_one)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(-128)


@pytest.mark.parametrize("memoize", [False, True])
def test_sub_clamps_above_max_int(memoize: bool) -> None:
    code = """
    func main()
        neg_127 = -(0, 127)
        return -(127, neg_127)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(127)


@pytest.mark.parametrize("memoize", [False, True])
def test_sub_clamps_below_min_int(memoize: bool) -> None:
    code = """
    func main()
        neg_127 = -(0, 127)
        min_int = -(neg_127, 1)
        return -(min_int, 1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(-128)


@pytest.mark.parametrize("memoize", [False, True])
def test_max_length_string_literal_accepted(memoize: bool) -> None:
    code = 'func main()\n    return "ABCDEFGHIJKLMNOP"\nendfunc'
    expected = RRE_LIST.create(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code, memoize=memoize) == expected


def test_error_string_literal_too_long() -> None:
    code = 'func main()\n    return "ABCDEFGHIJKLMNOPQ"\nendfunc'
    with pytest.raises(LexerErrorException):
        run_program(code)


@pytest.mark.parametrize("memoize", [False, True])
def test_append_to_max_length_list_is_noop(memoize: bool) -> None:
    code = """
    func main()
        full = "ABCDEFGHIJKLMNOP"
        return +(full, 81)
    endfunc
    """
    expected = RRE_LIST.create(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_prepend_to_max_length_list_is_noop(memoize: bool) -> None:
    code = """
    func main()
        full = "ABCDEFGHIJKLMNOP"
        return +(81, full)
    endfunc
    """
    expected = RRE_LIST.create(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_append_to_near_max_length_list_grows(memoize: bool) -> None:
    code = """
    func main()
        return +("ABCDEFGHIJKLMNO", 80)
    endfunc
    """
    expected = RRE_LIST.create(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_add_list_to_max_length_list_is_noop(memoize: bool) -> None:
    code = """
    func main()
        full = "ABCDEFGHIJKLMNOP"
        return +(full, "A")
    endfunc
    """
    expected = RRE_LIST.create(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_nesting_at_max_depth_then_wrap_is_noop(memoize: bool) -> None:
    code = """
    func main()
        d1 = []
        d2 = +([], d1)
        d3 = +([], d2)
        d4 = +([], d3)
        d5 = +([], d4)
        d6 = +([], d5)
        d7 = +([], d6)
        d8 = +([], d7)
        return +([], d8)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_LIST.create(())


@pytest.mark.parametrize("memoize", [False, True])
def test_thunk_append_and_prepend_at_max_length_are_noops(memoize: bool) -> None:
    code = """
    func lazy()%
        return 0
    endfunc

    func main()
        t0 = lazy()
        t1 = +(t0, 1)
        t2 = +(t1, 1)
        t3 = +(t2, 1)
        t4 = +(t3, 1)
        t5 = +(t4, 1)
        t6 = +(t5, 1)
        t7 = +(t6, 1)
        t8 = +(t7, 1)
        t9 = +(t8, 1)
        t10 = +(t9, 1)
        t11 = +(t10, 1)
        t12 = +(t11, 1)
        t13 = +(t12, 1)
        t14 = +(t13, 1)
        t15 = +(t14, 1)
        t16 = +(t15, 1)
        appended = +(t16, 2)
        prepended = +(99, t16)
        last_after_append = -(16, appended)
        first_after_prepend = -(0, prepended)
        return +(+( [], last_after_append), first_after_prepend)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_LIST.create(
        (RRE_INT(1), RRE_INT(1))
    )


def test_overlong_list_construction_raises() -> None:
    items = tuple(RRE_INT(0) for _ in range(MAX_LIST_LENGTH + 1))
    with pytest.raises(RuntimeErrorException):
        RRE_LIST.create(items)


def test_overdeep_list_construction_raises() -> None:
    nested: RRE_LIST = RRE_LIST.create(())
    for _ in range(MAX_LIST_NESTING_DEPTH - 1):
        nested = RRE_LIST.create((nested,))
    with pytest.raises(RuntimeErrorException):
        RRE_LIST.create((nested,))


def test_overdeep_thunk_construction_raises() -> None:
    nested: RRE_LIST = RRE_LIST.create(())
    for _ in range(MAX_LIST_NESTING_DEPTH - 1):
        nested = RRE_LIST.create((nested,))
    with pytest.raises(RuntimeErrorException):
        RRE_THUNK.create("f", (nested,))


def test_overlong_thunk_construction_raises() -> None:
    items = tuple(RRE_INT(0) for _ in range(MAX_LIST_LENGTH + 1))
    with pytest.raises(RuntimeErrorException):
        RRE_THUNK.create("f", items)


@pytest.mark.parametrize("memoize", [False, True])
def test_max_args_params_and_call_accepted(memoize: bool) -> None:
    code = """
    func main()
        return other(1, 2, 3)
    endfunc

    func other(a, b, c)
        return +(+(a, b), c)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(6)


def test_error_too_many_function_parameters() -> None:
    code = """
    func main(a, b, c, d)
        return a
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def test_error_too_many_call_arguments() -> None:
    code = """
    func main()
        return other(1, 2, 3, 4)
    endfunc

    func other(a)
        return a
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


def _main_returning_int_tokens(text: str) -> list[Token]:
    return [
        Token(TokenType.FUNCDEF, "func"),
        Token(TokenType.NAME, "main"),
        Token(TokenType.LEFTPAR, "("),
        Token(TokenType.RIGHTPAR, ")"),
        Token(TokenType.RETURN, "return"),
        Token(TokenType.CONSTINT, text),
        Token(TokenType.ENDFUNCDEF, "endfunc"),
        Token(TokenType.EOF, "EOF"),
    ]


def test_min_int_token_accepted() -> None:
    program = parse(_main_returning_int_tokens("-128"))
    return_expr = program.functions["main"].lines[-1].expr
    assert return_expr == RRE_INT(-128)


def test_error_int_token_below_min() -> None:
    with pytest.raises(ParserErrorException):
        parse(_main_returning_int_tokens("-129"))


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_truthy_returns_first_arg(memoize: bool) -> None:
    code = """
    func main()
        return ?(1, +(1, 1))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_truthy_does_not_enter_second_arg(memoize: bool) -> None:
    code = """
    func main()
        return ?(1, rec(1))
    endfunc

    func rec(n)
        return rec(n)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_falsy_evaluates_primitive_second_arg(memoize: bool) -> None:
    code = """
    func main()
        return ?(0, +(1, 1))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(2)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_falsy_evaluates_user_function_second_arg(memoize: bool) -> None:
    code = """
    func main()
        return ?(0, addone(1))
    endfunc

    func addone(n)
        return +(n, 1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(2)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_falsy_returns_non_call_second_arg(memoize: bool) -> None:
    code = """
    func main()
        int_branch = ?(0, 5)
        empty_branch = ?([], [])
        return +(+([], int_branch), empty_branch)
    endfunc
    """
    expected = RRE_LIST.create((RRE_INT(5), RRE_LIST.create(())))
    assert run_program(code, memoize=memoize) == expected


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_falsy_forces_lazy_function_body(memoize: bool) -> None:
    code = """
    func main()
        return ?(0, lazy(1, 2))
    endfunc

    func lazy(a, b)%
        return +(a, b)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(3)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_wrong_arity_thunk_is_error(memoize: bool) -> None:
    code = """
    func main()
        t = lazy(1, 2)
        extra = +(t, 3)
        return ?(0, extra)
    endfunc

    func lazy(a, b)%
        return +(a, b)
    endfunc
    """
    result = run_program(code, memoize=memoize)
    assert isinstance(result, RRE_ERROR)
    assert result.msg == "wrong number of arguments"


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_thunk_condition_does_not_enter_second_arg(memoize: bool) -> None:
    code = """
    func main()
        return -(0, ?(lazy(1), rec(1)))
    endfunc

    func lazy(a)%
        return a
    endfunc

    func rec(n)
        return rec(n)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_lazy_function_stores_evaluated_args_as_thunk(memoize: bool) -> None:
    code = """
    func main()
        return -(0, lazy(+(1, 2), 4))
    endfunc

    func lazy(a, b)%
        return +(a, b)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(3)


@pytest.mark.parametrize("memoize", [False, True])
def test_recursive_choice_terminates(memoize: bool) -> None:
    code = """
    func main(num)
      lz = >(0, num)
      return ?(lz, main(-(num, 1)))
    endfunc
    """
    assert run_program(code, inputs=[RRE_INT(0)], memoize=memoize) == RRE_INT(1)
    assert run_program(code, inputs=[RRE_INT(3)], memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_truthy_does_not_evaluate_second_arg_expressions(memoize: bool) -> None:
    code = """
    func main()
        return ?(1, +(bomb(), 1))
    endfunc

    func bomb()
        return bomb()
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_error_does_not_enter_second_arg(memoize: bool) -> None:
    code = """
    func main()
        bad = ~("choice error")
        return ?(bad, bomb())
    endfunc

    func bomb()
        return bomb()
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("choice error")


@pytest.mark.parametrize("memoize", [False, True])
def test_eager_function_forces_lazy_return(memoize: bool) -> None:
    code = """
    func id(x)
        return x
    endfunc

    func lazy(a)%
        return +(a, 2)
    endfunc

    func main()
        return id(lazy(1))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(3)


@pytest.mark.parametrize("memoize", [False, True])
def test_eager_return_forces_nested_percent_thunks(memoize: bool) -> None:
    code = """
    func main()
        return ?(0, lazy(1))
    endfunc

    func lazy(a)%
        return also(a)
    endfunc

    func also(b)%
        return +(b, 1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(2)


@pytest.mark.parametrize("memoize", [False, True])
def test_eager_return_forces_thunk_inside_list(memoize: bool) -> None:
    code = """
    func main()
        return +([], lazy(1))
    endfunc

    func lazy(a)%
        return +(a, 2)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_LIST.create((RRE_INT(3),))


@pytest.mark.parametrize("memoize", [False, True])
def test_eager_return_list_force_infects_on_thunk_error(memoize: bool) -> None:
    code = """
    func boxer(n)
        return +(+(5, []), lazy(n))
    endfunc

    func lazy(n)%
        return ~("thunk error")
    endfunc

    func main()
        return -(1, boxer(1))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("thunk error")


@pytest.mark.parametrize("memoize", [False, True])
def test_eager_return_wrong_arity_thunk_is_error(memoize: bool) -> None:
    code = """
    func main()
        return +(1, lazy(2))
    endfunc

    func lazy(a)%
        return a
    endfunc
    """
    result = run_program(code, memoize=memoize)
    assert isinstance(result, RRE_ERROR)
    assert result.msg == "wrong number of arguments"


@pytest.mark.parametrize("memoize", [False, True])
def test_percent_return_does_not_force_nested_thunk(memoize: bool) -> None:
    code = """
    func main()
        return -(0, ?(0, wrap(1)))
    endfunc

    func wrap(n)%
        return inner(n)
    endfunc

    func inner(n)%
        return +(n, 1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_error_constant_returns_message(memoize: bool) -> None:
    code = """
    func main()
        return ~("Error message")
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("Error message")


@pytest.mark.parametrize("memoize", [False, True])
def test_error_constant_infects_plus(memoize: bool) -> None:
    code = """
    func main()
        return +(~("a"), 1)
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("a")


@pytest.mark.parametrize("memoize", [False, True])
def test_error_constant_combines_two_errors(memoize: bool) -> None:
    code = """
    func main()
        return +(~("a"), ~("b"))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("a+b")


@pytest.mark.parametrize("memoize", [False, True])
def test_error_constant_empty_message(memoize: bool) -> None:
    code = """
    func main()
        return ~("")
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("")


@pytest.mark.parametrize(
    "bad",
    [
        "~()",
        '~("a", "b")',
        "~(1)",
        "~([])",
        "~(name)",
        '~(+("a", "b"))',
    ],
)
def test_error_constant_rejects_non_string_argument(bad: str) -> None:
    code = f"""
    func main()
        return {bad}
    endfunc
    """
    with pytest.raises(ParserErrorException):
        run_program(code)


@pytest.mark.parametrize("memoize", [False, True])
def test_recursion_depth_at_limit_succeeds(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func main()
        return leaf()
    endfunc

    func leaf()
        return 7
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(7)


@pytest.mark.parametrize("memoize", [False, True])
def test_recursion_depth_exceeded_is_error(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func main()
        return rec()
    endfunc

    func rec()
        return rec()
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("recursion depth")


@pytest.mark.parametrize("memoize", [False, True])
def test_recursion_depth_error_infects_plus(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func main()
        return +(1, rec())
    endfunc

    func rec()
        return rec()
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("recursion depth")


@pytest.mark.parametrize("memoize", [False, True])
def test_bindings_do_not_count_as_recursion(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 1)
    code = """
    func main()
        a = 1
        b = +(a, 1)
        c = +(b, 1)
        d = +(c, 1)
        e = +(d, 1)
        return e
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(5)


@pytest.mark.parametrize("memoize", [False, True])
def test_expression_and_force_frames_do_not_count_as_recursion(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 1)
    code = """
    func main()
        boxed = +([], ?(0, +(1, 2)))
        return boxed
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_LIST.create((RRE_INT(3),))


@pytest.mark.parametrize("memoize", [False, True])
def test_eager_percent_callee_counts_function_frames(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 1)
    code = """
    func lazy(a)%
        return +(a, 1)
    endfunc

    func main()
        return +(0, ?(0, lazy(1)))
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("recursion depth")

    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    assert run_program(code, memoize=memoize) == RRE_INT(2)


@pytest.mark.parametrize("memoize", [False, True])
def test_percent_thunk_not_counted_until_forced(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 1)
    code = """
    func lazy(a)%
        return +(a, 1)
    endfunc

    func main()
        t = lazy(1)
        return 5
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(5)


@pytest.mark.parametrize("memoize", [False, True])
def test_truthy_choice_skips_recursive_call_at_limit(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func rec()
        return rec()
    endfunc

    func leaf()
        return ?(1, rec())
    endfunc

    func main()
        return leaf()
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_INT(1)


@pytest.mark.parametrize("memoize", [False, True])
def test_choice_force_of_percent_thunk_counts_function_frame(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 1)
    code = """
    func rec()%
        return rec()
    endfunc

    func main()
        return ?(0, rec())
    endfunc
    """
    assert run_program(code, memoize=memoize) == RRE_ERROR("recursion depth")


def test_tail_self_call_in_binding_is_parse_error() -> None:
    code = """
    func main()
        return rec()
    endfunc

    func rec()@
        x = rec()
        return x
    endfunc
    """
    with pytest.raises(ParserErrorException, match="tail-recursive call"):
        run_program(code)


def test_tail_self_call_in_plus_is_parse_error() -> None:
    code = """
    func main()
        return rec()
    endfunc

    func rec()@
        return +(1, rec())
    endfunc
    """
    with pytest.raises(ParserErrorException, match="tail-recursive call"):
        run_program(code)


def test_tail_self_call_in_choice_condition_is_parse_error() -> None:
    code = """
    func main()
        return rec()
    endfunc

    func rec()@
        return ?(rec(), 0)
    endfunc
    """
    with pytest.raises(ParserErrorException, match="tail-recursive call"):
        run_program(code)


@pytest.mark.parametrize("memoize", [False, True])
def test_direct_tail_call_does_not_grow_depth(
    monkeypatch: pytest.MonkeyPatch, memoize: bool
) -> None:
    monkeypatch.setattr("pyrre.runtime.MAX_RECURSION_DEPTH", 2)
    code = """
    func rec()@
        return rec()
    endfunc

    func main()
        return rec()
    endfunc
    """
    if memoize:
        code = apply_memoize_modifier(code)
    stack = ProgramStack(parse(lex(code)), [])
    for _ in range(200):
        stack = execute_step(stack)
        func_frames = sum(
            isinstance(frame, FunctionStackFrame) for frame in stack.call_stack
        )
        assert func_frames <= 2
        if stack.final_value is not None:
            assert stack.final_value != RRE_ERROR("recursion depth")
            break
    else:
        assert stack.final_value is None
