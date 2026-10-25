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
    call: Call, evaluated_args: list[RRE_VALUE], func: FunctionDef
) -> FunctionStackFrame:
    arg_vals: dict[str, RRE_VALUE] = {}
    for val, name in zip(evaluated_args, func.param_names, strict=True):
        arg_vals[name] = val

    return FunctionStackFrame(call.funcname, arg_vals)


@wrap_with_runtime_exception
def handle_value_from_top_of_stack(val: RRE_VALUE, stack: ProgramStack) -> None:
    if not stack.call_stack:
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
def handle_primitive_op_call(
    evaluated_args: list[RRE_VALUE],
    frame_expr_call: Call,
    bindings: ImmutableMappingViewWithIdx[str, RRE_VALUE],
    stack: ProgramStack,
) -> None:
    if len(evaluated_args) == EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE:
        func = PRIMITIVE_OPS[frame_expr_call.funcname]

        handle_value_from_top_of_stack(
            func(
                evaluated_args[0],
                evaluated_args[1],
                stack.program.functions,
            ),
            stack,
        )
        return

    if len(evaluated_args) > EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE:
        raise RuntimeErrorException(
            f"expected {EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE} args for a primitive func, got {len(evaluated_args)}"
        )

    stack.call_stack.append(
        ExpressionStackFrame(
            frame_expr_call.params[len(evaluated_args)],
            bindings,
        )
    )


@wrap_with_runtime_exception
def handle_func_call(
    call: Call,
    evaluated_args: list[RRE_VALUE],
    bindings: ImmutableMappingViewWithIdx[str, RRE_VALUE],
    stack: ProgramStack,
) -> None:
    func = stack.program.functions[call.funcname]
    if len(evaluated_args) == len(func.param_names):
        stack.call_stack.append(
            construct_function_call_frame(call, evaluated_args, func)
        )
        return

    if len(evaluated_args) > len(func.param_names):
        raise RuntimeErrorException(
            "more than expected amount of args in handle_func_call"
        )

    stack.call_stack.append(
        ExpressionStackFrame(call.params[len(evaluated_args)], bindings)
    )


@wrap_with_runtime_exception
def process_expression_frame(frame: ExpressionStackFrame, stack: ProgramStack) -> None:
    if isinstance(frame.expr, Binding):
        binding_value = frame.bindings[frame.expr.bindname]
        handle_value_from_top_of_stack(binding_value, stack)
        return
    elif isinstance(frame.expr, get_args(RRE_VALUE)):
        handle_value_from_top_of_stack(cast(RRE_VALUE, frame.expr), stack)
    elif isinstance(frame.expr, Call):
        if frame.expr.funcname in PRIMITIVE_OPS:
            handle_primitive_op_call(
                frame.evaluated_args, frame.expr, frame.bindings, stack
            )
            return

        handle_func_call(frame.expr, frame.evaluated_args, frame.bindings, stack)
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
            pending_line.expr, ImmutableMappingViewWithIdx(frame.bindings)
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
