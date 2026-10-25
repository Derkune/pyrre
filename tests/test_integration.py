from typing import Any

from pyrre.types import (
    ProgramStack,
    RRE_LIST,
    RRE_INT,
    RRE_ERROR,
    RRE_THUNK,
    ParserErrorException,
    LexerErrorException,
    RuntimeErrorException,
    Token,
    TokenType,
)
from pyrre.static_config import MAX_LIST_LENGTH, MAX_LIST_NESTING_DEPTH
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
    result = run_program(CASE_1)
    assert result == RRE_LIST((RRE_INT(3), RRE_INT(65), RRE_INT(0)))


def test_int_arithmetic_basic() -> None:
    code = """
    func main()
        sum = +(40, 2)
        diff = -(10, 15)
        return +(sum, diff)
    endfunc
    """
    assert run_program(code) == RRE_INT(37)


def test_int_nested_calls() -> None:
    code = """
    func main()
        return -(+(10, +(20, 30)), 15)
    endfunc
    """
    assert run_program(code) == RRE_INT(45)


def test_add_int_to_list_prepend() -> None:
    code = """
    func main()
        list1 = +(65, [])
        return +(66, list1)
    endfunc
    """
    assert run_program(code) == RRE_LIST((RRE_INT(66), RRE_INT(65)))


def test_add_list_to_int_append() -> None:
    code = """
    func main()
        return +("A", 66)
    endfunc
    """
    assert run_program(code) == RRE_LIST((RRE_INT(65), RRE_INT(66)))


def test_add_list_to_list_nesting() -> None:
    code = """
    func main()
        return +("A", "B")
    endfunc
    """
    expected = RRE_LIST((RRE_INT(65), RRE_LIST((RRE_INT(66),))))
    assert run_program(code) == expected


def test_sub_int_list_retrieval_and_clamping() -> None:
    code = """
    func main()
        idx0 = -(0, "ABC")
        idx_clamped_high = -(99, "ABC")
        neg_idx = -(0, 5)
        idx_clamped_low = -(neg_idx, "ABC")
        return +(+(+([], idx_clamped_low), idx_clamped_high), idx0)
    endfunc
    """

    expected = RRE_LIST((RRE_INT(65), RRE_INT(67), RRE_INT(65)))
    assert run_program(code) == expected


def test_sub_list_int_removal_and_clamping() -> None:
    code = """
    func main()
        mid_removed = -("ABC", 1)
        clamped_high = -("ABC", 50)
        neg_idx = -(0, 10)
        clamped_low = -("ABC", neg_idx)
        return +(+(+([], mid_removed), clamped_high), clamped_low)
    endfunc
    """
    expected = RRE_LIST(
        (
            RRE_LIST((RRE_INT(65), RRE_INT(67))),
            RRE_LIST((RRE_INT(65), RRE_INT(66))),
            RRE_LIST((RRE_INT(66), RRE_INT(67))),
        )
    )
    assert run_program(code) == expected


def test_sub_list_list_difference() -> None:
    code = """
    func main()
        rem_one = -("ABACA", "A")
        rem_two = -("ABACA", "AA")
        rem_none = -("ABACA", [])
        return +(+(+([], rem_one), rem_two), rem_none)
    endfunc
    """
    rem_one = RRE_LIST((RRE_INT(66), RRE_INT(65), RRE_INT(67), RRE_INT(65)))
    rem_two = RRE_LIST((RRE_INT(66), RRE_INT(67), RRE_INT(65)))
    rem_none = RRE_LIST(
        (RRE_INT(65), RRE_INT(66), RRE_INT(65), RRE_INT(67), RRE_INT(65))
    )

    expected = RRE_LIST((rem_one, rem_two, rem_none))
    assert run_program(code) == expected


def test_comparisons_integers() -> None:
    code = """
    func main()
        gt = >(5, 3)
        eq = ≥(4, 4)
        lt = >(2, 8)
        return +( +(+([], gt), eq), lt)
    endfunc
    """
    expected = RRE_LIST((RRE_INT(1), RRE_INT(1), RRE_INT(0)))
    assert run_program(code) == expected


def test_comparisons_list_and_int() -> None:
    code = """
    func main()
        list_gt_int = >([], 100)
        int_gt_list = >(100, [])
        return +(+([], list_gt_int), int_gt_list)
    endfunc
    """
    expected = RRE_LIST((RRE_INT(1), RRE_INT(0)))
    assert run_program(code) == expected


def test_comparisons_lists() -> None:
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
    expected = RRE_LIST((RRE_INT(0), RRE_INT(1), RRE_INT(1), RRE_INT(0), RRE_INT(1)))
    assert run_program(code) == expected


def test_function_modifiers_and_distinct_letters() -> None:
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
    assert run_program(code, to_dump_history=False) == RRE_INT(25)


def test_main_with_arguments() -> None:
    code = """
    func main(x, y)
        return +(x, y)
    endfunc
    """
    inputs = [RRE_INT(12), RRE_INT(18)]
    assert run_program(code, inputs=inputs) == RRE_INT(30)


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


def test_max_int_literal_accepted() -> None:
    code = """
    func main()
        return 127
    endfunc
    """
    assert run_program(code) == RRE_INT(127)


def test_error_int_literal_above_max() -> None:
    code = """
    func main()
        return 128
    endfunc
    """
    with pytest.raises(LexerErrorException):
        run_program(code)


def test_add_clamps_above_max_int() -> None:
    code = """
    func main()
        return +(127, 1)
    endfunc
    """
    assert run_program(code) == RRE_INT(127)


def test_add_in_range_stays_at_max_int() -> None:
    code = """
    func main()
        return +(126, 1)
    endfunc
    """
    assert run_program(code) == RRE_INT(127)


def test_add_clamps_below_min_int() -> None:
    code = """
    func main()
        neg_one = -(0, 1)
        neg_127 = -(0, 127)
        min_int = -(neg_127, 1)
        return +(min_int, neg_one)
    endfunc
    """
    assert run_program(code) == RRE_INT(-128)


def test_sub_clamps_above_max_int() -> None:
    code = """
    func main()
        neg_127 = -(0, 127)
        return -(127, neg_127)
    endfunc
    """
    assert run_program(code) == RRE_INT(127)


def test_sub_clamps_below_min_int() -> None:
    code = """
    func main()
        neg_127 = -(0, 127)
        min_int = -(neg_127, 1)
        return -(min_int, 1)
    endfunc
    """
    assert run_program(code) == RRE_INT(-128)


def test_max_length_string_literal_accepted() -> None:
    code = 'func main()\n    return "ABCDEFGHIJKLMNOP"\nendfunc'
    expected = RRE_LIST(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code) == expected


def test_error_string_literal_too_long() -> None:
    code = 'func main()\n    return "ABCDEFGHIJKLMNOPQ"\nendfunc'
    with pytest.raises(LexerErrorException):
        run_program(code)


def test_append_to_max_length_list_is_noop() -> None:
    code = """
    func main()
        full = "ABCDEFGHIJKLMNOP"
        return +(full, 81)
    endfunc
    """
    expected = RRE_LIST(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code) == expected


def test_prepend_to_max_length_list_is_noop() -> None:
    code = """
    func main()
        full = "ABCDEFGHIJKLMNOP"
        return +(81, full)
    endfunc
    """
    expected = RRE_LIST(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code) == expected


def test_append_to_near_max_length_list_grows() -> None:
    code = """
    func main()
        return +("ABCDEFGHIJKLMNO", 80)
    endfunc
    """
    expected = RRE_LIST(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code) == expected


def test_add_list_to_max_length_list_is_noop() -> None:
    code = """
    func main()
        full = "ABCDEFGHIJKLMNOP"
        return +(full, "A")
    endfunc
    """
    expected = RRE_LIST(tuple(RRE_INT(ord(c)) for c in "ABCDEFGHIJKLMNOP"))
    assert run_program(code) == expected


def test_nesting_at_max_depth_then_wrap_is_noop() -> None:
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
    assert run_program(code) == RRE_LIST(())


def test_thunk_append_and_prepend_at_max_length_are_noops() -> None:
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
    assert run_program(code) == RRE_LIST((RRE_INT(1), RRE_INT(1)))


def test_overlong_list_construction_raises() -> None:
    items = tuple(RRE_INT(0) for _ in range(MAX_LIST_LENGTH + 1))
    with pytest.raises(RuntimeErrorException):
        RRE_LIST(items)


def test_overdeep_list_construction_raises() -> None:
    nested: RRE_LIST = RRE_LIST(())
    for _ in range(MAX_LIST_NESTING_DEPTH - 1):
        nested = RRE_LIST((nested,))
    with pytest.raises(RuntimeErrorException):
        RRE_LIST((nested,))


def test_overdeep_thunk_construction_raises() -> None:
    nested: RRE_LIST = RRE_LIST(())
    for _ in range(MAX_LIST_NESTING_DEPTH - 1):
        nested = RRE_LIST((nested,))
    with pytest.raises(RuntimeErrorException):
        RRE_THUNK("f", (nested,))


def test_overlong_thunk_construction_raises() -> None:
    items = tuple(RRE_INT(0) for _ in range(MAX_LIST_LENGTH + 1))
    with pytest.raises(RuntimeErrorException):
        RRE_THUNK("f", items)


def test_max_args_params_and_call_accepted() -> None:
    code = """
    func main()
        return other(1, 2, 3)
    endfunc

    func other(a, b, c)
        return +(+(a, b), c)
    endfunc
    """
    assert run_program(code) == RRE_INT(6)


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


def test_choice_truthy_returns_first_arg() -> None:
    code = """
    func main()
        return ?(1, +(1, 1))
    endfunc
    """
    assert run_program(code) == RRE_INT(1)


def test_choice_truthy_does_not_enter_second_arg() -> None:
    code = """
    func main()
        return ?(1, rec(1))
    endfunc

    func rec(n)
        return rec(n)
    endfunc
    """
    assert run_program(code) == RRE_INT(1)


def test_choice_falsy_evaluates_primitive_second_arg() -> None:
    code = """
    func main()
        return ?(0, +(1, 1))
    endfunc
    """
    assert run_program(code) == RRE_INT(2)


def test_choice_falsy_evaluates_user_function_second_arg() -> None:
    code = """
    func main()
        return ?(0, addone(1))
    endfunc

    func addone(n)
        return +(n, 1)
    endfunc
    """
    assert run_program(code) == RRE_INT(2)


def test_choice_falsy_returns_non_call_second_arg() -> None:
    code = """
    func main()
        int_branch = ?(0, 5)
        empty_branch = ?([], [])
        return +(+([], int_branch), empty_branch)
    endfunc
    """
    expected = RRE_LIST((RRE_INT(5), RRE_LIST(())))
    assert run_program(code) == expected


def test_choice_falsy_forces_lazy_function_body() -> None:
    code = """
    func main()
        return ?(0, lazy(1, 2))
    endfunc

    func lazy(a, b)%
        return +(a, b)
    endfunc
    """
    assert run_program(code) == RRE_INT(3)


def test_choice_wrong_arity_thunk_is_error() -> None:
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
    result = run_program(code)
    assert isinstance(result, RRE_ERROR)
    assert result.msg == "wrong number of arguments"


def test_choice_thunk_condition_does_not_enter_second_arg() -> None:
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
    assert run_program(code) == RRE_INT(1)


def test_lazy_function_stores_evaluated_args_as_thunk() -> None:
    code = """
    func main()
        return -(0, lazy(+(1, 2), 4))
    endfunc

    func lazy(a, b)%
        return +(a, b)
    endfunc
    """
    assert run_program(code) == RRE_INT(3)


def test_recursive_choice_terminates() -> None:
    code = """
    func main(num)
      lz = >(0, num)
      return ?(lz, main(-(num, 1)))
    endfunc
    """
    assert run_program(code, inputs=[RRE_INT(0)]) == RRE_INT(1)
    assert run_program(code, inputs=[RRE_INT(3)]) == RRE_INT(1)


def test_choice_truthy_does_not_evaluate_second_arg_expressions() -> None:
    code = """
    func main()
        return ?(1, +(bomb(), 1))
    endfunc

    func bomb()
        return bomb()
    endfunc
    """
    assert run_program(code) == RRE_INT(1)


def test_choice_error_does_not_enter_second_arg() -> None:
    # TODO: adapt to new operation edge case handling
    code = """
    func main()
        bad = -(0, [])
        return ?(bad, bomb())
    endfunc

    func bomb()
        return bomb()
    endfunc
    """
    result = run_program(code)
    assert isinstance(result, RRE_ERROR)
    assert result.msg == "val1 is out of bounds"


def test_eager_function_forces_lazy_return() -> None:
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
    assert run_program(code) == RRE_INT(3)


def test_eager_return_forces_nested_percent_thunks() -> None:
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
    assert run_program(code) == RRE_INT(2)


def test_eager_return_forces_thunk_inside_list() -> None:
    code = """
    func main()
        return +([], lazy(1))
    endfunc

    func lazy(a)%
        return +(a, 2)
    endfunc
    """
    assert run_program(code) == RRE_LIST((RRE_INT(3),))


def test_eager_return_list_force_infects_on_thunk_error() -> None:
    # TODO: adapt to new operation edge case handling
    code = """
    func boxer(n)
        return +(+(5, []), lazy(n))
    endfunc

    func lazy(n)%
        return -(0, [])
    endfunc

    func main()
        return -(1, boxer(1))
    endfunc
    """
    result = run_program(code)
    assert isinstance(result, RRE_ERROR)
    assert result.msg == "val1 is out of bounds"


def test_eager_return_wrong_arity_thunk_is_error() -> None:
    code = """
    func main()
        return +(1, lazy(2))
    endfunc

    func lazy(a)%
        return a
    endfunc
    """
    result = run_program(code)
    assert isinstance(result, RRE_ERROR)
    assert result.msg == "wrong number of arguments"


def test_percent_return_does_not_force_nested_thunk() -> None:
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
    assert run_program(code) == RRE_INT(1)
