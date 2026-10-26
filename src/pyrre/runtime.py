import copy
from typing import Iterable, Type, Callable, get_args, cast
from functools import wraps
from dataclasses import dataclass, field

from pyrre.types import (
    ProgramStack,
    FunctionStackFrame,
    ExpressionStackFrame,
    ForceFrame,
    MemoKey,
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
    args_strictly_smaller,
)
from pyrre.static_config import MAX_RECURSION_DEPTH

RECURSION_DEPTH_ERROR = RRE_ERROR("recursion depth")
WELLFOUNDEDNESS_ERROR = RRE_ERROR("wellfoundedness")
CANT_OUTPUT_THUNKS_ERROR = RRE_ERROR("Can't output thunks")


def memo_key_for(name: funcname, args: Iterable[RRE_VALUE]) -> MemoKey:
    return (name, tuple(args))


def lookup_memo(
    func: FunctionDef, key: MemoKey, stack: ProgramStack
) -> RRE_VALUE | None:
    if FUNC_MODS.MEMOIZE not in func.modifiers:
        return None
    return stack.memo.get(key)


def store_memo(key: MemoKey | None, val: RRE_VALUE, stack: ProgramStack) -> None:
    if key is None:
        return
    if isinstance(val, RRE_ERROR) and RECURSION_DEPTH_ERROR.msg in val.msg:
        return
    stack.memo[key] = val


def store_frame_memos(
    memo_key: MemoKey | None,
    prior_memo_keys: tuple[MemoKey, ...],
    val: RRE_VALUE,
    stack: ProgramStack,
) -> None:
    store_memo(memo_key, val, stack)
    for key in prior_memo_keys:
        store_memo(key, val, stack)


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

    memo_key = None
    if FUNC_MODS.MEMOIZE in main_func.modifiers:
        memo_key = memo_key_for(main_name, stack.program_inputs)
    return FunctionStackFrame(main_name, bindings, memo_key=memo_key)


def construct_function_call_frame(
    *, call: Call, evaluated_args: list[RRE_VALUE], func: FunctionDef
) -> FunctionStackFrame:
    arg_vals: dict[str, RRE_VALUE] = {}
    for val, name in zip(evaluated_args, func.param_names, strict=True):
        arg_vals[name] = val

    memo_key = None
    if FUNC_MODS.MEMOIZE in func.modifiers:
        memo_key = memo_key_for(call.funcname, evaluated_args)
    return FunctionStackFrame(call.funcname, arg_vals, memo_key=memo_key)


def function_frame_count(stack: ProgramStack) -> int:
    return sum(isinstance(frame, FunctionStackFrame) for frame in stack.call_stack)


def try_push_function_frame(frame: FunctionStackFrame, stack: ProgramStack) -> bool:
    if function_frame_count(stack) >= MAX_RECURSION_DEPTH:
        return False
    stack.call_stack.append(frame)
    return True


def is_tail_self_call(*, func: FunctionDef, caller_func: funcname) -> bool:
    return FUNC_MODS.TAIL_RECURSE in func.modifiers and caller_func == func.name


def frame_argument_tuple(
    frame: FunctionStackFrame, func: FunctionDef
) -> tuple[RRE_VALUE, ...]:
    return tuple(frame.bindings[name] for name in func.param_names)


def wellfoundedness_error(
    *,
    func: FunctionDef,
    evaluated_args: list[RRE_VALUE],
    stack: ProgramStack,
) -> RRE_ERROR | None:
    if FUNC_MODS.ASSERT_WELLFOUNDEDNESS not in func.modifiers:
        return None

    for frame in reversed(stack.call_stack):
        if not isinstance(frame, FunctionStackFrame):
            continue
        if frame.funcname != func.name:
            continue
        old_args = frame_argument_tuple(frame, func)
        if args_strictly_smaller(
            tuple(evaluated_args), old_args, stack.program.functions
        ):
            return None
        return WELLFOUNDEDNESS_ERROR
    return None


def replace_tail_function_frame(
    new_frame: FunctionStackFrame, stack: ProgramStack
) -> None:
    for _ in range(len(stack.call_stack)):
        if not stack.call_stack or not isinstance(
            stack.call_stack[-1], ExpressionStackFrame
        ):
            break
        stack.call_stack.pop()

    if not stack.call_stack or not isinstance(stack.call_stack[-1], FunctionStackFrame):
        raise RuntimeErrorException("tail recurse expected a function frame")

    old = stack.call_stack[-1]
    if old.funcname != new_frame.funcname:
        raise RuntimeErrorException("tail recurse function mismatch")

    priors = list(old.prior_memo_keys)
    if old.memo_key is not None:
        priors.append(old.memo_key)
    new_frame.prior_memo_keys = tuple(priors)
    stack.call_stack.pop()
    stack.call_stack.append(new_frame)


def program_output_value(val: RRE_VALUE) -> RRE_VALUE:
    match val:
        case RRE_THUNK():
            return CANT_OUTPUT_THUNKS_ERROR
        case RRE_ERROR():
            return val
        case RRE_LIST():
            for item in val.value:
                converted = program_output_value(item)
                if isinstance(converted, RRE_ERROR):
                    return converted
            return val
        case _:
            return val


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
    cached = lookup_memo(func, memo_key_for(thunk.funcname, thunk.arguments), stack)
    if cached is not None:
        complete_force_frame(cached, stack)
        return
    evaluated_args = list(thunk.arguments)
    wf_error = wellfoundedness_error(
        func=func, evaluated_args=evaluated_args, stack=stack
    )
    if wf_error is not None:
        complete_force_frame(wf_error, stack)
        return
    frame = construct_function_call_frame(
        call=Call(thunk.funcname, ()),
        evaluated_args=evaluated_args,
        func=func,
    )
    if not try_push_function_frame(frame, stack):
        complete_force_frame(RECURSION_DEPTH_ERROR, stack)


def set_program_result(val: RRE_VALUE, stack: ProgramStack) -> None:
    stack.final_value = program_output_value(val)


def receive_into_force_frame(frame: ForceFrame, val: RRE_VALUE) -> None:
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

    store_frame_memos(top_frame.memo_key, top_frame.prior_memo_keys, val, stack)
    stack.call_stack.pop(-1)
    continue_after_call_result(val, stack)


def complete_force_frame(val: RRE_VALUE, stack: ProgramStack) -> None:
    top_frame = stack.call_stack[-1]
    if not isinstance(top_frame, ForceFrame):
        raise RuntimeErrorException(
            "complete_force_frame assumed to come from ForceFrame"
        )

    store_frame_memos(top_frame.memo_key, top_frame.prior_memo_keys, val, stack)
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
    cached = lookup_memo(func, memo_key_for(thunk.funcname, thunk.arguments), stack)
    if cached is not None:
        handle_value_from_top_of_stack(cached, stack)
        return
    evaluated_args = list(thunk.arguments)
    wf_error = wellfoundedness_error(
        func=func, evaluated_args=evaluated_args, stack=stack
    )
    if wf_error is not None:
        handle_value_from_top_of_stack(wf_error, stack)
        return
    frame = construct_function_call_frame(
        call=Call(thunk.funcname, ()),
        evaluated_args=evaluated_args,
        func=func,
    )
    if is_tail_self_call(func=func, caller_func=top_frame.caller_func):
        replace_tail_function_frame(frame, stack)
        return
    if not try_push_function_frame(frame, stack):
        handle_value_from_top_of_stack(RECURSION_DEPTH_ERROR, stack)


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
    caller_func: funcname,
    stack: ProgramStack,
) -> Callable[[], None]:
    def response() -> None:
        cached = lookup_memo(func, memo_key_for(call.funcname, evaluated_args), stack)
        if cached is not None:
            handle_value_from_top_of_stack(cached, stack)
            return
        wf_error = wellfoundedness_error(
            func=func, evaluated_args=evaluated_args, stack=stack
        )
        if wf_error is not None:
            handle_value_from_top_of_stack(wf_error, stack)
            return
        frame = construct_function_call_frame(
            call=call, evaluated_args=evaluated_args, func=func
        )
        if is_tail_self_call(func=func, caller_func=caller_func):
            replace_tail_function_frame(frame, stack)
            return
        if not try_push_function_frame(frame, stack):
            handle_value_from_top_of_stack(RECURSION_DEPTH_ERROR, stack)

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
        val = RRE_THUNK.create(call.funcname, tuple(evaluated_args))
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
                caller_func=frame.caller_func,
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

        memo_key = frame.memo_key
        prior_memo_keys = frame.prior_memo_keys
        stack.call_stack.pop(-1)
        if isinstance(val, RRE_THUNK):
            stack.call_stack.append(
                ForceFrame(val, memo_key=memo_key, prior_memo_keys=prior_memo_keys)
            )
        else:
            store_frame_memos(memo_key, prior_memo_keys, val, stack)
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

    if isinstance(val, (RRE_INT, RRE_ERROR, RRE_LIST)):
        complete_force_frame(val, stack)
        return

    if isinstance(val, RRE_THUNK):
        arity_error = thunk_arity_error(val, stack)
        if arity_error is not None:
            complete_force_frame(arity_error, stack)
            return
        push_thunk_evaluation(val, stack)
        return

    raise RuntimeErrorException("unknown value in process_force_frame")


def execute_step(stack: ProgramStack) -> ProgramStack:
    if stack.final_value is not None:
        raise RuntimeErrorException("execute_step after final_value is present")

    stack = stack.copy_stack()

    if not stack.call_stack:
        if not try_push_function_frame(construct_point_of_entry_frame(stack), stack):
            set_program_result(RECURSION_DEPTH_ERROR, stack)
            return stack

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
