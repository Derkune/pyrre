from __future__ import annotations

import string
import enum
from dataclasses import dataclass, field
from typing import Iterator, TypeAlias, TypeVar, Generic
from collections.abc import Mapping


TK = TypeVar("TK")
TV = TypeVar("TV")


class ImmutableMapping(Mapping, Generic[TK, TV]):
    def __init__(self, inp_dict: Mapping[TK, TV] | None = None) -> None:
        self._dct: dict[TK, TV] = {}
        if inp_dict:
            {k: v for (k, v) in inp_dict.items()}

    def __iter__(self) -> Iterator:
        return self._dct.__iter__()

    def __len__(self) -> int:
        return self._dct.__len__()

    def __getitem__(self, key: TK) -> TV:
        return self._dct.__getitem__(key)

    def __repr__(self) -> str:
        return "IMMUTABLE: " + self._dct.__repr__()


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


class LexerErrorException(Exception):
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(msg, *args)

        self.msg: str = msg


class ParserErrorException(Exception):
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(msg, *args)

        self.msg: str = msg


class RuntimErrorException(Exception):
    pass


@dataclass(frozen=True)
class RRE_INT:
    value: int


@dataclass(frozen=True)
class RRE_LIST:
    value: list[RRE_VALUE]


@dataclass(frozen=True)
class RRE_THUNK:
    funcname: funcname
    arguments: list[RRE_VALUE]


@dataclass(frozen=True)
class RRE_ERROR:
    msg: str


RRE_VALUE: TypeAlias = RRE_INT | RRE_LIST | RRE_THUNK | RRE_ERROR
RRE_TYPE: TypeAlias = type[RRE_INT] | type[RRE_LIST] | type[RRE_THUNK] | type[RRE_ERROR]


class FUNC_MODS(enum.Enum):
    ASSERT_WELLFOUNDEDNESS = "!"
    TAIL_RECURSE = "@"
    MEMOIZE = "#"
    NON_EAGER = "%"


@dataclass(frozen=True)
class Binding:
    bindname: str


@dataclass(frozen=True)
class Call:
    funcname: funcname
    params: list[Expr]


Expr: TypeAlias = Binding | RRE_VALUE | Call


@dataclass(frozen=True)
class ExprLine:
    expr_name: str
    expr: Expr


@dataclass(frozen=True)
class ReturnExpr:
    expr: Expr


@dataclass(frozen=True)
class FunctionDef:
    name: funcname
    modifiers: list[FUNC_MODS]
    param_names: list[str]
    lines: list[ExprLine | ReturnExpr]


@dataclass(frozen=True)
class Program:
    functions: ImmutableMapping[funcname, FunctionDef]
