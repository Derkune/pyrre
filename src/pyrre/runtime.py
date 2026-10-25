import copy
from typing import Iterable, Type, Callable, get_args, cast
from functools import wraps
from dataclasses import dataclass, field

from pyrre.types import (
    ProgramStack,
    FunctionStackFrame,
    ExpressionStackFrame,
    ForceFrame,
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
    RRE_ERROR,
    RRE_FORCE_THUNK,
    RRE_INT,
    RRE_LIST,
    FUNC_MODS,
    is_truthy,
    Program,
)


def callee_returns_thunk(*, call_func: funcname, stack: ProgramStack) -> bool:
    if call_func in PRIMITIVE_OPS:
        return False

    function = stack.program.functions[call_func]
    return FUNC_MODS.NON_EAGER in function.modifiers


def arg_reduces_to_thunk(*, call_func: funcname, arg_idx: int) -> bool:
    return call_func == "?" and arg_idx == 1


def find_main(function_names: Iterable[funcname]) -> funcname:
    for name in function_names:
        if name.lower() == "main":
            return name

    raise RuntimeErrorException("Can't find main")


def construct_point_of_entry_frame(stack: ProgramStack) -> FunctionStackFrame:
    main_name = find_main(stack.program.functions.keys())
    main_func = stack.program.functions[main_name]

    bindings: dict[str, RRE_VALUE] = {}
    for param, passed_val in zip(
        main_func.param_names, stack.program_inputs, strict=True
    ):
        bindings[param] = passed_val

    return FunctionStackFrame(main_name, bindings)


def construct_function_call_frame(
    *, call: Call, evaluated_args: list[RRE_VALUE], func: FunctionDef
) -> FunctionStackFrame:
    arg_vals: dict[str, RRE_VALUE] = {}
    for val, name in zip(evaluated_args, func.param_names, strict=True):
        arg_vals[name] = val

    return FunctionStackFrame(call.funcname, arg_vals)


def value_contains_thunk(val: RRE_VALUE) -> bool:
    match val:
        case RRE_THUNK():
            return True
        case RRE_LIST():
            return any(value_contains_thunk(item) for item in val.value)
        case _:
            return False


def thunk_arity_error(thunk: RRE_THUNK, stack: ProgramStack) -> RRE_ERROR | None:
    arg_count = len(thunk.arguments)
    if thunk.funcname in PRIMITIVE_OPS:
        if arg_count != EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE:
            return RRE_ERROR("wrong number of arguments")
        return None

    func = stack.program.functions[thunk.funcname]
    if arg_count != len(func.param_names):
        return RRE_ERROR("wrong number of arguments")
    return None


def push_thunk_evaluation(thunk: RRE_THUNK, stack: ProgramStack) -> None:
    if thunk.funcname in PRIMITIVE_OPS:
        stack.call_stack.append(
            ExpressionStackFrame(
                Call(thunk.funcname, ()),
                "",
                ImmutableMappingViewWithIdx(),
                evaluated_args=list(thunk.arguments),
            )
        )
        return

    func = stack.program.functions[thunk.funcname]
    stack.call_stack.append(
        construct_function_call_frame(
            call=Call(thunk.funcname, ()),
            evaluated_args=list(thunk.arguments),
            func=func,
        )
    )


def set_program_result(val: RRE_VALUE, stack: ProgramStack) -> None:
    if isinstance(val, RRE_THUNK):
        raise RuntimeErrorException("Thunk not allowed as a program return")

    stack.final_value = val


def receive_into_force_frame(frame: ForceFrame, val: RRE_VALUE) -> None:
    if isinstance(frame.value, RRE_LIST):
        if isinstance(val, RRE_ERROR):
            frame.value = val
            frame.forced_items = []
        else:
            frame.forced_items.append(val)
        return

    frame.value = val


def deliver_to_parent(val: RRE_VALUE, stack: ProgramStack) -> None:
    if not stack.call_stack:
        set_program_result(val, stack)
        return

    top_frame = stack.call_stack[-1]

    if isinstance(top_frame, FunctionStackFrame):
        function = stack.program.functions[top_frame.funcname]

        line = function.lines[top_frame.current_line]
        top_frame.bindings[line.bind_name] = val
        top_frame.current_line += 1
    elif isinstance(top_frame, ExpressionStackFrame):
        top_frame.evaluated_args.append(val)
    elif isinstance(top_frame, ForceFrame):
        receive_into_force_frame(top_frame, val)
    else:
        raise RuntimeErrorException("Unkown type of a frame in call stack")


def handle_value_from_top_of_stack(val: RRE_VALUE, stack: ProgramStack) -> None:
    if not stack.call_stack:
        set_program_result(val, stack)
        return

    stack.call_stack.pop(-1)
    deliver_to_parent(val, stack)


def continue_after_call_result(val: RRE_VALUE, stack: ProgramStack) -> None:
    if not stack.call_stack:
        set_program_result(val, stack)
        return

    top_frame = stack.call_stack[-1]
    if isinstance(top_frame, ForceFrame):
        receive_into_force_frame(top_frame, val)
        return

    handle_value_from_top_of_stack(val, stack)


def handle_value_from_return_of_function(val: RRE_VALUE, stack: ProgramStack) -> None:
    top_frame = stack.call_stack[-1]
    if not isinstance(top_frame, FunctionStackFrame):
        raise RuntimeErrorException(
            "handle_value_from_return_of_function assumed to come from FunctionStackFrame"
        )

    stack.call_stack.pop(-1)
    continue_after_call_result(val, stack)


def complete_force_frame(val: RRE_VALUE, stack: ProgramStack) -> None:
    top_frame = stack.call_stack[-1]
    if not isinstance(top_frame, ForceFrame):
        raise RuntimeErrorException(
            "complete_force_frame assumed to come from ForceFrame"
        )

    stack.call_stack.pop(-1)
    continue_after_call_result(val, stack)


def schedule_forced_thunk(thunk: RRE_THUNK, stack: ProgramStack) -> None:
    top_frame = stack.call_stack[-1]
    if not isinstance(top_frame, ExpressionStackFrame):
        raise RuntimeErrorException(
            "schedule_forced_thunk assumed to come from ExpressionStackFrame"
        )

    arity_error = thunk_arity_error(thunk, stack)
    if arity_error is not None:
        handle_value_from_top_of_stack(arity_error, stack)
        return

    if thunk.funcname in PRIMITIVE_OPS:
        stack.call_stack.pop(-1)
        stack.call_stack.append(
            ExpressionStackFrame(
                Call(thunk.funcname, ()),
                top_frame.caller_func,
                top_frame.bindings,
                evaluated_args=list(thunk.arguments),
            )
        )
        return

    func = stack.program.functions[thunk.funcname]
    stack.call_stack.append(
        construct_function_call_frame(
            call=Call(thunk.funcname, ()),
            evaluated_args=list(thunk.arguments),
            func=func,
        )
    )


def response_if_op_args_evaluated(
    *, funcname: funcname, evaluated_args: list[RRE_VALUE], stack: ProgramStack
) -> Callable[[], None]:
    def response() -> None:
        func = PRIMITIVE_OPS[funcname]
        result = func(
            evaluated_args[0],
            evaluated_args[1],
            stack.program.functions,
        )
        if isinstance(result, RRE_FORCE_THUNK):
            schedule_forced_thunk(result.thunk, stack)
            return

        handle_value_from_top_of_stack(result, stack)

    return response


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

    if call.funcname == "?" and len(evaluated_args) == 1:
        if is_truthy(evaluated_args[0]):
            handle_value_from_top_of_stack(evaluated_args[0], stack)
            return

    stack.call_stack.append(
        ExpressionStackFrame(
            call.params[len(evaluated_args)],
            caller_func,
            bindings,
            reduce_to_thunk=arg_reduces_to_thunk(
                call_func=call.funcname, arg_idx=len(evaluated_args)
            ),
        )
    )


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


def get_func_expected_number_of_args(funcname: funcname, stack: ProgramStack) -> int:
    if funcname in PRIMITIVE_OPS:
        return EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE

    func = stack.program.functions[funcname]
    return len(func.param_names)


def response_if_call_should_be_thunk(
    *, call: Call, evaluated_args: list[RRE_VALUE], stack: ProgramStack
) -> Callable[[], None]:
    def response() -> None:
        val = RRE_THUNK(call.funcname, tuple(evaluated_args))
        handle_value_from_top_of_stack(val, stack)

    return response


def process_expression_frame(frame: ExpressionStackFrame, stack: ProgramStack) -> None:
    if isinstance(frame.expr, Binding):
        binding_value = frame.bindings[frame.expr.bindname]
        handle_value_from_top_of_stack(binding_value, stack)
    elif isinstance(frame.expr, get_args(RRE_VALUE)):
        handle_value_from_top_of_stack(cast(RRE_VALUE, frame.expr), stack)
    elif isinstance(frame.expr, Call):
        if frame.reduce_to_thunk or callee_returns_thunk(
            call_func=frame.expr.funcname, stack=stack
        ):
            response_if_args_evaluated = response_if_call_should_be_thunk(
                call=frame.expr, evaluated_args=frame.evaluated_args, stack=stack
            )
        elif frame.expr.funcname in PRIMITIVE_OPS:
            response_if_args_evaluated = response_if_op_args_evaluated(
                funcname=frame.expr.funcname,
                evaluated_args=frame.evaluated_args,
                stack=stack,
            )
        else:
            response_if_args_evaluated = response_if_func_call_parameters_evaluated(
                call=frame.expr,
                evaluated_args=frame.evaluated_args,
                func=stack.program.functions[frame.expr.funcname],
                stack=stack,
            )

        handle_func_call(
            call=frame.expr,
            evaluated_args=frame.evaluated_args,
            caller_func=frame.caller_func,
            bindings=frame.bindings,
            expected_number_of_args=get_func_expected_number_of_args(
                frame.expr.funcname, stack
            ),
            response_if_args_evaluated=response_if_args_evaluated,
            stack=stack,
        )
    else:
        raise RuntimeErrorException(
            "unknown type in frame.expr in process_statement_frame"
        )


def process_function_frame(frame: FunctionStackFrame, stack: ProgramStack) -> None:
    function = stack.program.functions[frame.funcname]

    if frame.current_line == len(function.lines):
        val = frame.bindings[RETURN_BINDING]
        if FUNC_MODS.NON_EAGER in function.modifiers:
            handle_value_from_return_of_function(val, stack)
            return

        stack.call_stack.pop(-1)
        if value_contains_thunk(val):
            stack.call_stack.append(ForceFrame(val))
        else:
            continue_after_call_result(val, stack)
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


def process_force_frame(frame: ForceFrame, stack: ProgramStack) -> None:
    val = frame.value

    if isinstance(val, (RRE_INT, RRE_ERROR)):
        complete_force_frame(val, stack)
        return

    if isinstance(val, RRE_THUNK):
        arity_error = thunk_arity_error(val, stack)
        if arity_error is not None:
            complete_force_frame(arity_error, stack)
            return
        push_thunk_evaluation(val, stack)
        return

    if not isinstance(val, RRE_LIST):
        raise RuntimeErrorException("unknown value in process_force_frame")

    items = val.value
    start = len(frame.forced_items)
    for item in items[start:]:
        if value_contains_thunk(item):
            stack.call_stack.append(ForceFrame(item))
            return
        frame.forced_items.append(item)

    complete_force_frame(RRE_LIST(tuple(frame.forced_items)), stack)


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
    elif isinstance(top_frame, ForceFrame):
        process_force_frame(top_frame, stack)
    else:
        raise RuntimeErrorException("Unkown type of a frame in call stack")

    return stack


@dataclass
class Runtime:
    program: Program
    program_inputs: list[RRE_VALUE]
    history: list[ProgramStack] = field(default_factory=list)

    def run_program(self, max_steps: int = 1000000) -> RRE_VALUE:
        stack: ProgramStack = ProgramStack(self.program, self.program_inputs)

        for _ in range(max_steps):
            self.history.append(stack)
            stack = execute_step(stack)
            if stack.final_value:
                return stack.final_value

        raise RuntimeErrorException("Ran over max amount of steps")
