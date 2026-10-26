import json
import dataclasses

from pyrre.types import (
    ProgramStack,
    FunctionStackFrame,
    ExpressionStackFrame,
    ForceFrame,
    Program,
    FunctionDef,
    funcname,
    RRE_LIST,
    RRE_THUNK,
    RRE_INT,
    RRE_ERROR,
    RRE_VALUE,
)
from pyrre.static_config import MAX_CHAR_REPRESENTABLE_INT, MIN_CHAR_REPRESENTABLE_INT


def dataclass_default(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        res = {"CLASS NAME": type(obj).__name__}
        res.update(dataclasses.asdict(obj))
        return res
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps_obj_json_with_dataclass(obj) -> str:
    return json.dumps(obj, default=dataclass_default)


def dump_func_frame(frame: FunctionStackFrame) -> list[str]:
    lines: list[str] = []

    lines.append(f"###### FRAME FUNC {frame.funcname}")
    lines.append(f"###### CURRENT LINE {frame.current_line}")
    lines.append(f"###### BINDINGS {dumps_obj_json_with_dataclass(frame.bindings)}")
    lines.append("")

    return lines


def dump_expression_frame(frame: ExpressionStackFrame) -> list[str]:
    lines: list[str] = []

    lines.append(f"###### FRAME EXRESSION {frame.expr}")
    lines.append(f"###### FRAME CALLER FUNC {frame.caller_func}")
    lines.append(f"###### FRAME REDUCE TO THUNK {frame.reduce_to_thunk}")
    lines.append(
        f"###### FRAME EVALUATED ARGS {dumps_obj_json_with_dataclass(frame.evaluated_args)}"
    )
    lines.append(
        f"###### FRAME BINDINGS {dumps_obj_json_with_dataclass(frame.bindings._dct)}"
    )
    lines.append("")

    return lines


def dump_force_frame(frame: ForceFrame) -> list[str]:
    lines: list[str] = []

    lines.append(f"###### FRAME FORCE {dumps_obj_json_with_dataclass(frame.value)}")
    lines.append("")

    return lines


def dump_stack(stack: ProgramStack, stack_idx: int) -> list[str]:
    lines: list[str] = []

    lines.append(f"### STACK {stack_idx}")
    lines.append("")
    lines.append("### PROGRAM INPUTS")
    lines.append(
        ", ".join(dumps_obj_json_with_dataclass(v) for v in stack.program_inputs)
    )
    lines.append("### PROGRAM OUTPUT")
    lines.append(
        dumps_obj_json_with_dataclass(stack.final_value)
        if stack.final_value
        else "None"
    )

    for frame in stack.call_stack:
        if isinstance(frame, FunctionStackFrame):
            lines.extend(dump_func_frame(frame))
        elif isinstance(frame, ExpressionStackFrame):
            lines.extend(dump_expression_frame(frame))
        elif isinstance(frame, ForceFrame):
            lines.extend(dump_force_frame(frame))

    lines.append("### END OF STACK")
    lines.extend([""] * 3)

    return lines


def dump_function(func_key: funcname, func: FunctionDef) -> list[str]:
    lines: list[str] = []

    lines.append(f"++++++ FUNCTION KEY {func_key}")
    lines.append(f"++++++ FUNCTION NAME {func.name}")
    lines.append(f"++++++ FUNCTION PARAMS {func.param_names}")
    lines.append(f"++++++ FUNCTION MODS {func.modifiers}")

    for line in func.lines:
        lines.append(f"+++++++++ FUNCTION LINE {dumps_obj_json_with_dataclass(line)}")

    lines.append("")

    return lines


def dump_program(program: Program) -> list[str]:
    lines: list[str] = []

    lines.append("+++ PROGRAM")
    lines.append("")

    for function in program.functions.keys():
        implementation = program.functions[function]
        lines.extend(dump_function(function, implementation))

    lines.append("+++ END OF PROGRAM")
    lines.extend([""] * 3)

    return lines


def dump_history(
    history: list[ProgramStack] | ProgramStack, include_program: None | Program = None
) -> str:
    if not isinstance(history, list):
        history = [history]

    lines: list[str] = []

    if include_program:
        lines.extend(dump_program(include_program))

    for idx, snapshot in enumerate(history):
        lines.extend(dump_stack(snapshot, idx))

    return "\n".join(lines)


def prettify_chars(val: RRE_VALUE) -> str:
    match val:
        case RRE_INT():
            if (
                val.value <= MAX_CHAR_REPRESENTABLE_INT
                and val.value >= MIN_CHAR_REPRESENTABLE_INT
            ):
                return chr(val.value)
            else:
                return "□"
        case RRE_LIST():
            parts: list[str] = []

            for item in val.value:
                parts.append(prettify_chars(item))

            return "".join(parts)
        case RRE_THUNK():
            return "█"
        case RRE_ERROR():
            return "░"
