from copy import deepcopy
from types import MappingProxyType

from pyrre.types import (
    CallStack,
    Program,
    RuntimErrorException,
    StackFrame,
    Line,
    Expr,
    Call,
    RRE_VALUE,
    RRE_INT,
    RRE_LIST,
    RRE_THUNK,
    Var,
    FunctionDef,
    funcname,
)


def primitive_operation(symbol: funcname, *args: RRE_VALUE) -> RRE_VALUE:
    return RRE_INT(999)


def find_main_name(program: Program) -> funcname:
    for func in program.functions.keys():
        if func.lower() == "main":
            return func

    raise RuntimErrorException("main not found")


def evaluate_constants(
    frame: StackFrame,
    parts_to_evaluate: list[Expr],
) -> None | Call | funcname:
    while len(frame.evaluated_part_values) < len(parts_to_evaluate):
        param_expr: Expr = parts_to_evaluate[len(frame.evaluated_part_values)]
        match param_expr:
            case RRE_INT() | RRE_LIST() | RRE_THUNK() as val:
                frame.evaluated_part_values.append(val)
                continue
            case Var() as var:
                frame.evaluated_part_values.append(
                    frame.local_vars[var.varname]
                )  # TODO: handle _
                continue
            case Call() as innercall:
                return innercall

    return None


def get_further_evaluation(
    frame: StackFrame, functions: MappingProxyType[funcname, FunctionDef]
) -> None | Call | funcname:
    match frame.evaluator:
        case funcname() as function_name:
            func = functions[function_name]
            return evaluate_constants(
                frame,
                [l.value for l in func.lines] + [func.return_expr],
            )
        case Call() as call:
            return evaluate_constants(frame, call.params)
        case _:
            raise RuntimErrorException("unknown evaluator")


def _cast(expr: Expr) -> RRE_VALUE:
    match expr:
        case RRE_INT() | RRE_LIST() | RRE_THUNK() as val:
            return val
        case _:
            raise RuntimErrorException("expr was assumed to be a value but isn't")


def get_value_from_fully_evaluated_frame(
    frame: StackFrame, functions: MappingProxyType[funcname, FunctionDef]
) -> RRE_VALUE:
    match frame.evaluator:
        case funcname() as function_name:
            function = functions[function_name]
            return frame.evaluated_part_values[len(function.lines)]  # return value
        case Call() as call:  # assumed to be a primitive
            params = [_cast(p) for p in call.params]
            return primitive_operation(call.funcname, *params)


def handle_value_on_top_of_stack(value: RRE_VALUE, stack: CallStack) -> None:
    if not stack.frames:
        stack.final_value = value
        return

    top_frame = stack.frames[-1]
    top_frame.evaluated_part_values.append(value)
    if isinstance(top_frame.evaluator, funcname):
        function = stack.program.functions[top_frame.evaluator]
        if len(top_frame.evaluated_part_values) >= len(function.params):
            # just appended the return value
            return

        line_idx = len(top_frame.evaluated_part_values) - 1
        line = function.lines[line_idx]
        top_frame.local_vars[line.varname] = value


def advance_step(stack: CallStack) -> CallStack:
    stack = stack.copy_stack()

    if not stack.frames:
        stack.frames.append(StackFrame(find_main_name(stack.program), {}))

    top_frame = stack.frames[-1]
    to_further_evaluate: None | Call | funcname = get_further_evaluation(
        top_frame, stack.program.functions
    )

    match to_further_evaluate:
        case None:
            value = get_value_from_fully_evaluated_frame(
                top_frame, stack.program.functions
            )
            stack.frames.pop(-1)
            handle_value_on_top_of_stack(value, stack)
        case Call():
            stack.frames.append(StackFrame(to_further_evaluate, top_frame.local_vars))
        case funcname():
            stack.frames.append(StackFrame(to_further_evaluate, {}))

    return stack
