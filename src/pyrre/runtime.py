import copy
from typing import Iterable, Type, Callable, get_args, cast
from functools import wraps

from pyrre.types import (
    ProgramStack,
    FunctionStackFrame,
    ExpressionStackFrame,
    FunctionDef,
    funcname,
    ImmutableMappingViewWithIdx,
    RuntimeErrorException,
    RRE_VALUE,
    RRE_TypeErrorException,
    RETURN_BINDING,
    BindingLine,
    Binding,
    Call,
    PRIMITIVE_OPS,
    EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE,
    RRE_THUNK,
    FUNC_MODS,
)


def wrap_with_runtime_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeErrorException, RRE_TypeErrorException) as expected:
            raise expected
        except Exception as err:
            raise RuntimeErrorException(f"Error in '{func.__name__}': {err}") from err

    return wrapper


@wrap_with_runtime_exception
def call_should_be_thunk(
    *, call_func: funcname, caller_arg_idx: int, stack: ProgramStack
) -> bool:
    if call_func in PRIMITIVE_OPS:
        if call_func == "?" and caller_arg_idx == 1:
            return True
        return False

    function = stack.program.functions[call_func]
    if FUNC_MODS.NON_EAGER in function.modifiers:
        return True

    return False


@wrap_with_runtime_exception
def find_main(function_names: Iterable[funcname]) -> funcname:
    for name in function_names:
        if name.lower() == "main":
            return name

    raise RuntimeErrorException("Can't find main")


@wrap_with_runtime_exception
def construct_point_of_entry_frame(stack: ProgramStack) -> FunctionStackFrame:
    main_name = find_main(stack.program.functions.keys())
    main_func = stack.program.functions[main_name]

    bindings: dict[str, RRE_VALUE] = {}
    for param, passed_val in zip(
        main_func.param_names, stack.program_inputs, strict=True
    ):
        bindings[param] = passed_val

    return FunctionStackFrame(main_name, bindings)


@wrap_with_runtime_exception
def construct_function_call_frame(
    *, call: Call, evaluated_args: list[RRE_VALUE], func: FunctionDef
) -> FunctionStackFrame:
    arg_vals: dict[str, RRE_VALUE] = {}
    for val, name in zip(evaluated_args, func.param_names, strict=True):
        arg_vals[name] = val

    return FunctionStackFrame(call.funcname, arg_vals)


@wrap_with_runtime_exception
def handle_value_from_top_of_stack(val: RRE_VALUE, stack: ProgramStack) -> None:
    if not stack.call_stack:
        if isinstance(val, RRE_THUNK):
            raise RuntimeErrorException("Thunk not allowed as a program return")

        stack.final_value = val
        return

    stack.call_stack.pop(-1)
    top_frame = stack.call_stack[-1]

    if isinstance(top_frame, FunctionStackFrame):
        function = stack.program.functions[top_frame.funcname]

        line = function.lines[top_frame.current_line]
        top_frame.bindings[line.bind_name] = val
        top_frame.current_line += 1
    elif isinstance(top_frame, ExpressionStackFrame):
        top_frame.evaluated_args.append(val)
    else:
        raise RuntimeErrorException("Unkown type of a frame in call stack")


@wrap_with_runtime_exception
def handle_value_from_return_of_function(val: RRE_VALUE, stack: ProgramStack) -> None:
    top_frame = stack.call_stack[-1]
    if not isinstance(top_frame, FunctionStackFrame):
        raise RuntimeErrorException(
            "handle_value_from_return_of_function assumed to come from FunctionStackFrame"
        )

    stack.call_stack.pop(-1)
    handle_value_from_top_of_stack(val, stack)


@wrap_with_runtime_exception
def response_if_op_args_evaluated(
    *, funcname: funcname, evaluated_args: list[RRE_VALUE], stack: ProgramStack
) -> Callable[[], None]:
    def response() -> None:
        func = PRIMITIVE_OPS[funcname]

        handle_value_from_top_of_stack(
            func(
                evaluated_args[0],
                evaluated_args[1],
                stack.program.functions,
            ),
            stack,
        )

    return response


@wrap_with_runtime_exception
def handle_func_call(
    *,
    call: Call,
    evaluated_args: list[RRE_VALUE],
    caller_func: funcname,
    bindings: ImmutableMappingViewWithIdx[str, RRE_VALUE],
    expected_number_of_args: int,
    response_if_args_evaluated: Callable[[], None],
    stack: ProgramStack,
) -> None:
    if len(evaluated_args) == expected_number_of_args:
        response_if_args_evaluated()
        return

    if len(evaluated_args) > expected_number_of_args:
        raise RuntimeErrorException(
            "more than expected amount of args in handle_func_call"
        )

    stack.call_stack.append(
        ExpressionStackFrame(call.params[len(evaluated_args)], caller_func, bindings)
    )


@wrap_with_runtime_exception
def response_if_func_call_parameters_evaluated(
    *,
    call: Call,
    evaluated_args: list[RRE_VALUE],
    func: FunctionDef,
    stack: ProgramStack,
) -> Callable[[], None]:
    def response() -> None:
        stack.call_stack.append(
            construct_function_call_frame(
                call=call, evaluated_args=evaluated_args, func=func
            )
        )

    return response


@wrap_with_runtime_exception
def get_func_expected_number_of_args(funcname: funcname, stack: ProgramStack) -> int:
    if funcname in PRIMITIVE_OPS:
        return EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE

    func = stack.program.functions[funcname]
    return len(func.param_names)


@wrap_with_runtime_exception
def response_if_call_should_be_thunk(
    *, call: Call, evaluated_args: list[RRE_VALUE], stack: ProgramStack
) -> Callable[[], None]:
    def response() -> None:
        val = RRE_THUNK(call.funcname, tuple(evaluated_args))
        handle_value_from_top_of_stack(val, stack)

    return response


@wrap_with_runtime_exception
def process_expression_frame(frame: ExpressionStackFrame, stack: ProgramStack) -> None:
    if isinstance(frame.expr, Binding):
        binding_value = frame.bindings[frame.expr.bindname]
        handle_value_from_top_of_stack(binding_value, stack)
    elif isinstance(frame.expr, get_args(RRE_VALUE)):
        handle_value_from_top_of_stack(cast(RRE_VALUE, frame.expr), stack)
    elif isinstance(frame.expr, Call):
        if call_should_be_thunk(
            call_func=frame.expr.funcname,
            caller_arg_idx=len(frame.evaluated_args),
            stack=stack,
        ):
            handle_func_call(
                call=frame.expr,
                evaluated_args=frame.evaluated_args,
                caller_func=frame.caller_func,
                bindings=frame.bindings,
                expected_number_of_args=get_func_expected_number_of_args(
                    frame.expr.funcname, stack
                ),
                response_if_args_evaluated=response_if_call_should_be_thunk(
                    call=frame.expr, evaluated_args=frame.evaluated_args, stack=stack
                ),
                stack=stack,
            )
            return

        if frame.expr.funcname in PRIMITIVE_OPS:
            handle_func_call(
                call=frame.expr,
                evaluated_args=frame.evaluated_args,
                caller_func=frame.caller_func,
                bindings=frame.bindings,
                expected_number_of_args=get_func_expected_number_of_args(
                    frame.expr.funcname, stack
                ),
                response_if_args_evaluated=response_if_op_args_evaluated(
                    funcname=frame.expr.funcname,
                    evaluated_args=frame.evaluated_args,
                    stack=stack,
                ),
                stack=stack,
            )
            return

        func = stack.program.functions[frame.expr.funcname]

        handle_func_call(
            call=frame.expr,
            evaluated_args=frame.evaluated_args,
            caller_func=frame.caller_func,
            bindings=frame.bindings,
            expected_number_of_args=get_func_expected_number_of_args(
                frame.expr.funcname, stack
            ),
            response_if_args_evaluated=response_if_func_call_parameters_evaluated(
                call=frame.expr,
                evaluated_args=frame.evaluated_args,
                func=func,
                stack=stack,
            ),
            stack=stack,
        )
    else:
        raise RuntimeErrorException(
            "unknown type in frame.expr in process_statement_frame"
        )


@wrap_with_runtime_exception
def process_function_frame(frame: FunctionStackFrame, stack: ProgramStack) -> None:
    function = stack.program.functions[frame.funcname]

    if frame.current_line == len(function.lines):
        handle_value_from_return_of_function(frame.bindings[RETURN_BINDING], stack)
        return

    if frame.current_line > len(function.lines):
        raise RuntimeErrorException("too many bindings in process_function_frame")

    pending_line: BindingLine = function.lines[frame.current_line]
    stack.call_stack.append(
        ExpressionStackFrame(
            pending_line.expr,
            frame.funcname,
            ImmutableMappingViewWithIdx(frame.bindings),
        )
    )


@wrap_with_runtime_exception
def execute_step(stack: ProgramStack) -> ProgramStack:
    if stack.final_value is not None:
        raise RuntimeErrorException("execute_step after final_value is present")

    stack = stack.copy_stack()

    if not stack.call_stack:
        stack.call_stack.append(construct_point_of_entry_frame(stack))

    top_frame = stack.call_stack[-1]

    if isinstance(top_frame, FunctionStackFrame):
        process_function_frame(top_frame, stack)
    elif isinstance(top_frame, ExpressionStackFrame):
        process_expression_frame(top_frame, stack)
    else:
        raise RuntimeErrorException("Unkown type of a frame in call stack")

    return stack
