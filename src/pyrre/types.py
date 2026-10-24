from __future__ import annotations

import string
import enum
from dataclasses import dataclass, field
from typing import (
    ItemsView,
    Iterator,
    TypeAlias,
    TypeVar,
    Generic,
    KeysView,
    ValuesView,
)
from collections.abc import Mapping
import copy


TK = TypeVar("TK")
TV = TypeVar("TV")


class ImmutableMappingWithIdx(Mapping, Generic[TK, TV]):
    def __init__(self, inp_dict: Mapping[TK, TV] | None = None) -> None:
        self._dct: dict[TK, TV] = {}
        if inp_dict:
            self._dct = {k: v for (k, v) in inp_dict.items()}

    def get_idx(self, k: TK) -> int:
        for idx, key in enumerate(self._dct.keys()):
            if key == k:
                return idx

        raise KeyError(k)

    def keys(self) -> KeysView[TK]:
        return self._dct.keys()

    def values(self) -> ValuesView[TV]:
        return self._dct.values()

    def items(self) -> ItemsView[TK, TV]:
        return self._dct.items()

    def __iter__(self) -> Iterator:
        return self._dct.__iter__()

    def __len__(self) -> int:
        return self._dct.__len__()

    def __getitem__(self, key: TK) -> TV:
        return self._dct.__getitem__(key)

    def __repr__(self) -> str:
        return "IMMUTABLE: " + self._dct.__repr__()


T = TypeVar("T")


immutable_list: TypeAlias = tuple[T, ...]


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
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(msg, *args)

        self.msg: str = msg


@dataclass(frozen=True)
class RRE_INT:
    value: int


@dataclass(frozen=True)
class RRE_LIST:
    value: immutable_list[RRE_VALUE]


@dataclass(frozen=True)
class RRE_THUNK:
    funcname: funcname
    arguments: immutable_list[RRE_VALUE]


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
    params: immutable_list[Expr]


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
    modifiers: immutable_list[FUNC_MODS]
    param_names: immutable_list[str]
    lines: immutable_list[ExprLine | ReturnExpr]


@dataclass(frozen=True)
class Program:
    functions: ImmutableMappingWithIdx[funcname, FunctionDef]


class RRE_TypeErrorException(Exception):
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(msg, *args)

        self.msg: str = msg


def RRE_PLUS(
    val1: RRE_VALUE,
    val2: RRE_VALUE,
    _: ImmutableMappingWithIdx[funcname, FunctionDef],
) -> RRE_VALUE:
    match val1, val2:
        case RRE_INT(), RRE_INT():
            return RRE_INT(val1.value + val2.value)
        case RRE_INT(), RRE_LIST():
            return RRE_LIST(tuple([val1]) + val2.value)
        case RRE_INT(), RRE_THUNK():
            return RRE_THUNK(val2.funcname, tuple([val1]) + val2.arguments)
        case RRE_INT(), RRE_ERROR():
            return val2
        #
        case RRE_LIST(), RRE_INT():
            return RRE_LIST(val1.value + tuple([val2]))
        case RRE_LIST(), RRE_LIST():
            return RRE_LIST(val1.value + tuple([val2]))
        case RRE_LIST(), RRE_THUNK():
            return RRE_LIST(val1.value + tuple([val2]))
        case RRE_LIST(), RRE_ERROR():
            return val2
        #
        case RRE_THUNK(), RRE_INT():
            return RRE_THUNK(val1.funcname, val1.arguments + tuple([val2]))
        case RRE_THUNK(), RRE_LIST():
            return RRE_THUNK(val1.funcname, val1.arguments + tuple([val2]))
        case RRE_THUNK(), RRE_THUNK():
            return RRE_THUNK(val1.funcname, val1.arguments + tuple([val2]))
        case RRE_THUNK(), RRE_ERROR():
            return val2
        #
        case RRE_ERROR(), RRE_INT():
            return val1
        case RRE_ERROR(), RRE_LIST():
            return val1
        case RRE_ERROR(), RRE_THUNK():
            return val1
        case RRE_ERROR(), RRE_ERROR():
            return RRE_ERROR(f"{val1.msg}|{val2.msg}")
        #
        case _:
            raise RRE_TypeErrorException("Unknown type in RRE_PLUS")


def lexicographical_comparison(
    lst1: immutable_list[RRE_VALUE],
    lst2: immutable_list[RRE_VALUE],
    functions: ImmutableMappingWithIdx[funcname, FunctionDef],
) -> int:
    for item1, item2 in zip(lst1, lst2):
        result = value_comparison(item1, item2, functions)
        if result:
            return result

    if len(lst1) > len(lst2):
        return 1
    if len(lst1) < len(lst2):
        return -1

    return 0


def value_comparison(
    val1: RRE_VALUE,
    val2: RRE_VALUE,
    functions: ImmutableMappingWithIdx[funcname, FunctionDef],
) -> int:
    match val1, val2:
        case RRE_INT(), RRE_INT():
            return (
                1 if val1.value > val2.value else 0 if val1.value == val2.value else -1
            )
        case RRE_INT(), RRE_LIST():
            return -1
        case RRE_INT(), RRE_THUNK():
            return -1
        case RRE_INT(), RRE_ERROR():
            return -1
        #
        case RRE_LIST(), RRE_INT():
            return 1
        case RRE_LIST(), RRE_LIST():
            return lexicographical_comparison(val1.value, val2.value, functions)
        case RRE_LIST(), RRE_THUNK():
            return -1
        case RRE_LIST(), RRE_ERROR():
            return -1
        #
        case RRE_THUNK(), RRE_INT():
            return 1
        case RRE_THUNK(), RRE_LIST():
            return 1
        case RRE_THUNK(), RRE_THUNK():
            if functions.get_idx(val1.funcname) > functions.get_idx(val2.funcname):
                return 1
            if functions.get_idx(val1.funcname) < functions.get_idx(val2.funcname):
                return -1
            return lexicographical_comparison(val1.arguments, val2.arguments, functions)

        case RRE_THUNK(), RRE_ERROR():
            return -1
        #
        case RRE_ERROR(), RRE_INT():
            return 1
        case RRE_ERROR(), RRE_LIST():
            return 1
        case RRE_ERROR(), RRE_THUNK():
            return 1
        case RRE_ERROR(), RRE_ERROR():
            return 0
        #
        case _:
            raise RRE_TypeErrorException("Unknown type in RRE_COMPARE")


def list_difference(
    list1: immutable_list[RRE_VALUE],
    list2: immutable_list[RRE_VALUE],
    functions: ImmutableMappingWithIdx[funcname, FunctionDef],
) -> immutable_list[RRE_VALUE]:
    lst1: list[RRE_VALUE] = list(list1)
    lst2: list[RRE_VALUE] = list(list2)
    ret_lst: list[RRE_VALUE] = copy.deepcopy(lst1)

    for item2 in lst2:
        to_remove_idx: None | int = None
        for idx, item1 in enumerate(ret_lst):
            if value_comparison(item1, item2, functions) == 0:
                to_remove_idx = idx
                break

        if to_remove_idx is not None:
            ret_lst.pop(to_remove_idx)

    return tuple(ret_lst)


def try_clamp_lst_idx(val: int, lst_len: int) -> None | int:
    if not lst_len:
        return None

    val = min(val, lst_len - 1)
    val = max(val, 0)
    return val


def RRE_MINUS(
    val1: RRE_VALUE,
    val2: RRE_VALUE,
    functions: ImmutableMappingWithIdx[funcname, FunctionDef],
) -> RRE_VALUE:
    match val1, val2:
        case RRE_INT(), RRE_INT():
            return RRE_INT(val1.value - val2.value)
        case RRE_INT(), RRE_LIST():
            lst_idx = try_clamp_lst_idx(val1.value, len(val2.value))
            if lst_idx is None:
                return val1
            return val2.value[lst_idx]
        case RRE_INT(), RRE_THUNK():
            lst_idx = try_clamp_lst_idx(val1.value, len(val2.arguments))
            if lst_idx is None:
                return val1
            return val2.arguments[lst_idx]
        case RRE_INT(), RRE_ERROR():
            return val2
        #
        case RRE_LIST(), RRE_INT():
            lst_idx = try_clamp_lst_idx(val2.value, len(val1.value))
            if lst_idx is None:
                return val1

            lst = list(val1.value)
            lst.pop(lst_idx)
            return RRE_LIST(tuple(lst))
        case RRE_LIST(), RRE_LIST():
            return RRE_LIST(list_difference(val1.value, val2.value, functions))
        case RRE_LIST(), RRE_THUNK():
            return RRE_LIST(list_difference(val1.value, val2.arguments, functions))
        case RRE_LIST(), RRE_ERROR():
            return val2
        #
        case RRE_THUNK(), RRE_INT():
            lst_idx = try_clamp_lst_idx(val2.value, len(val1.arguments))
            if lst_idx is None:
                return val1

            lst = list(val1.arguments)
            lst.pop(lst_idx)
            return RRE_THUNK(val1.funcname, tuple(lst))
        case RRE_THUNK(), RRE_LIST():
            return RRE_THUNK(
                val1.funcname, list_difference(val1.arguments, val2.value, functions)
            )
        case RRE_THUNK(), RRE_THUNK():
            return RRE_THUNK(
                val1.funcname,
                list_difference(val1.arguments, val2.arguments, functions),
            )
        case RRE_THUNK(), RRE_ERROR():
            return val2
        #
        case RRE_ERROR(), RRE_INT():
            return val1
        case RRE_ERROR(), RRE_LIST():
            return val1
        case RRE_ERROR(), RRE_THUNK():
            return val1
        case RRE_ERROR(), RRE_ERROR():
            return RRE_ERROR(f"{val1.msg}|{val2.msg}")
        #
        case _:
            raise RRE_TypeErrorException("Unknown type in RRE_MINUS")


def is_truthy(val: RRE_VALUE) -> bool:
    match val:
        case RRE_INT() | RRE_LIST():
            return bool(val.value)
        case RRE_THUNK() | RRE_ERROR():
            return True


def RRE_COMPARE(
    val1: RRE_VALUE,
    val2: RRE_VALUE,
    functions: ImmutableMappingWithIdx[funcname, FunctionDef],
) -> RRE_VALUE:
    if isinstance(val1, RRE_ERROR) and isinstance(val2, RRE_ERROR):
        return RRE_ERROR(f"{val1.msg}|{val2.msg}")
    if isinstance(val1, RRE_ERROR):
        return val1
    if isinstance(val2, RRE_ERROR):
        return val2

    return RRE_INT(1) if value_comparison(val1, val2, functions) >= 0 else RRE_INT(0)


def RRE_CONDITION(
    val1: RRE_VALUE,
    val2: RRE_THUNK,
    _: ImmutableMappingWithIdx[funcname, FunctionDef],
) -> RRE_VALUE:
    if isinstance(val1, RRE_ERROR):
        return val1

    if is_truthy(val1):
        return val1

    evaluated = evaluate_thunk(val2)  # TODO
    return evaluated
