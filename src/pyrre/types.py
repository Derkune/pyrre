from __future__ import annotations

import string
import enum
from dataclasses import dataclass, field
from typing import TypeAlias
from types import MappingProxyType


funcname: TypeAlias = str


OMMITTED_ARG: str = "_"
NAME_CHARS: frozenset[str] = frozenset(
    char
    for collection in [
        string.ascii_letters,
        [c.upper() for c in string.ascii_letters],
        string.digits,
        OMMITTED_ARG,
    ]
    for char in collection
)
PRIMITIVE_OPS: str = "+-?≥" + ">"  # last one is alias
QUOTE = '"'


class TokenType(enum.Enum):
    FUNCDEF = "func"
    NAME = "NAME"
    ENDFUNCDEF = "endfunc"
    LEFTPAR = "("
    RIGHTPAR = ")"
    RETURN = "return"
    FUNCMOD = "!@#%"
    COMMA = ","
    CONSTINT = string.digits
    CONSTEMPTYLST = "[]"
    CONSTSTR = "CONSTSTR"
    EQUALS = "="
    EOF = "EOF"


SINGLE_CHAR_TOKENS: dict[str, TokenType] = dict(
    [
        (TokenType.LEFTPAR.value, TokenType.LEFTPAR),
        (TokenType.RIGHTPAR.value, TokenType.RIGHTPAR),
        (TokenType.COMMA.value, TokenType.COMMA),
        (TokenType.EQUALS.value, TokenType.EQUALS),
    ]
    + [(char, TokenType.FUNCMOD) for char in TokenType.FUNCMOD.value]
    + [(char, TokenType.NAME) for char in PRIMITIVE_OPS]
)


@dataclass
class Token:
    token_type: TokenType
    text: str

    def __repr__(self) -> str:
        return f'{self.token_type.name}: "{self.text}"'


@dataclass
class LexerError:  # TODO: experiment with abolishing exceptions unsuccessful, switch this back too for consistency
    msg: str


class ParserErrorException(Exception):
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(msg, *args)

        self.msg: str = msg


class RuntimErrorException(Exception):
    pass


@dataclass
class ParserError:
    msg: str


@dataclass(frozen=True)
class RRE_INT:
    value: int


@dataclass(frozen=True)
class RRE_LIST:
    value: list[RRE_VALUE]


@dataclass(frozen=True)
class RRE_THUNK:
    funcref: Call
    arguments: list[RRE_VALUE | None]


@dataclass(frozen=True)
class RRE_ERROR:
    msg: str


RRE_VALUE: TypeAlias = RRE_INT | RRE_LIST | RRE_THUNK
RRE_TYPE: TypeAlias = type[RRE_INT] | type[RRE_LIST] | type[RRE_THUNK]


class FUNC_MODS(enum.Enum):
    ASSERT_WELLFOUNDEDNESS = "!"
    TAIL_RECURSE = "@"
    MEMOIZE = "#"
    NON_EAGER = "%"


@dataclass(frozen=True)
class Var:
    varname: str


@dataclass(frozen=True)
class Call:
    funcname: funcname
    params: list[Expr]


Expr: TypeAlias = Var | RRE_VALUE | Call


@dataclass(frozen=True)
class ConstDef:  # TODO: rename to Line
    name: str  # TODO: rename to varname
    value: Expr


@dataclass(frozen=True)
class FunctionDef:
    name: funcname
    modifiers: list[FUNC_MODS]
    params: list[str]
    lines: list[ConstDef]
    return_expr: Expr


@dataclass(frozen=True)
class Program:
    functions: MappingProxyType[funcname, FunctionDef]


@dataclass(frozen=True)
class StackFrame:
    evaluator: funcname | Call
    local_vars: dict[str, RRE_VALUE]
    evaluated_part_values: list[RRE_VALUE] = field(default_factory=list)

    def copy_frame(self) -> StackFrame:
        return StackFrame(self.evaluator, self.local_vars, self.evaluated_part_values)


@dataclass
class CallStack:
    program: Program
    frames: list[StackFrame] = field(default_factory=list)
    final_value: None | RRE_VALUE = None

    def copy_stack(self) -> CallStack:
        return CallStack(
            self.program, [f.copy_frame() for f in self.frames], self.final_value
        )
