from copy import deepcopy

from pyrre.types import (
    CallStack,
    Program,
    RuntimErrorException,
    StackFrame,
    ConstDef,
    Expr,
    Call,
    RRE_VALUE,
    RRE_INT,
    RRE_LIST,
    RRE_THUNK,
    Var,
    FunctionDef,
)


def find_main_name(program: Program) -> str:
    for func in program.functions.keys():
        if func.lower() == "main":
            return func

    raise RuntimErrorException("main not found")


def evaluate_constants(
    frame: StackFrame,
    parts_to_evaluate: list[Expr],
) -> None | Call | str:
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
    frame: StackFrame, functions: dict[str, FunctionDef]
) -> None | Call | str:
    match frame.evaluator:
        case str() as funcname:
            func = functions[funcname]
            return evaluate_constants(
                frame,
                [l.value for l in func.lines] + [func.return_expr],
            )
        case Call() as call:
            return evaluate_constants(frame, call.params)
        case _:
            raise RuntimErrorException("unknown evaluator")


def get_value_from_fully_evaluated_frame(frame: StackFrame) -> RRE_VALUE:
    match frame.evaluator:
        case str():
            pass
        case Call():
            pass


def handle_value_on_top_of_stack(value: RRE_VALUE, stack: CallStack) -> None:
    return "NOT IMPLEMENTED"


def advance_step(stack: CallStack) -> CallStack:
    stack = deepcopy(stack)

    if not stack.frames:
        stack.frames.append(StackFrame(find_main_name(stack.program), {}))

    top_frame = stack.frames[-1]
    to_further_evaluate: None | Call | str = get_further_evaluation(
        top_frame, stack.program.functions
    )

    match to_further_evaluate:
        case None:
            value = get_value_from_fully_evaluated_frame(top_frame)
            stack.frames.pop(-1)
            handle_value_on_top_of_stack(value, stack)
        case Call():
            stack.frames.append(StackFrame(to_further_evaluate, top_frame.local_vars))
        case str():
            stack.frames.append(StackFrame(to_further_evaluate, {}))

    return stack
