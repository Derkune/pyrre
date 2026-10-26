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
    Callable,
)
from collections.abc import Mapping
import copy

from pyrre.static_config import (
    MAX_INT,
    MIN_INT,
    MAX_LIST_LENGTH,
    MAX_LIST_NESTING_DEPTH,
)


TK = TypeVar("TK")
TV = TypeVar("TV")


class ImmutableMappingViewWithIdx(Mapping, Generic[TK, TV]):
    def __init__(self, inp_dict: dict[TK, TV] | None = None) -> None:
        self._dct: dict[TK, TV] = {}
        if inp_dict:
            self._dct = inp_dict

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


NAME_CHARS: frozenset[str] = frozenset(
    char
    for collection in [
        string.ascii_letters,
        [c.upper() for c in string.ascii_letters],
        string.digits,
        "_",
    ]
    for char in collection
)
QUOTE = '"'
RETURN_BINDING: str = "+++RETURN+++"


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


PRIMITIVE_OP_SYMBOLS: str = "+-?≥" + ">"  # last one is an alias
ERROR_CONST_SYMBOL: str = "~"
SINGLE_CHAR_TOKENS: dict[str, TokenType] = dict(
    [
        (TokenType.LEFTPAR.value, TokenType.LEFTPAR),
        (TokenType.RIGHTPAR.value, TokenType.RIGHTPAR),
        (TokenType.COMMA.value, TokenType.COMMA),
        (TokenType.EQUALS.value, TokenType.EQUALS),
    ]
    + [(char, TokenType.FUNCMOD) for char in TokenType.FUNCMOD.value]
    + [(char, TokenType.NAME) for char in PRIMITIVE_OP_SYMBOLS + ERROR_CONST_SYMBOL]
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


class RuntimeErrorException(Exception):
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(msg, *args)

        self.msg: str = msg


@dataclass(frozen=True)
class RRE_INT:
    value: int


def _item_nesting_depth(val: RRE_VALUE) -> int:
    if isinstance(val, (RRE_LIST, RRE_THUNK)):
        return val.depth
    return 0


def _sequence_nesting_depth(items: immutable_list[RRE_VALUE]) -> int:
    if not items:
        return 1
    return 1 + max(_item_nesting_depth(item) for item in items)


def _sequence_depth_within_limits(items: immutable_list[RRE_VALUE]) -> int:
    if len(items) > MAX_LIST_LENGTH:
        raise RuntimeErrorException("list too long")
    depth = _sequence_nesting_depth(items)
    if depth > MAX_LIST_NESTING_DEPTH:
        raise RuntimeErrorException("list nested too deeply")
    return depth


@dataclass(frozen=True)
class RRE_LIST:
    value: immutable_list[RRE_VALUE]
    depth: int

    @classmethod
    def create(cls, value: immutable_list[RRE_VALUE]) -> RRE_LIST:
        return cls(value, _sequence_depth_within_limits(value))


@dataclass(frozen=True)
class RRE_THUNK:
    funcname: funcname
    arguments: immutable_list[RRE_VALUE]
    depth: int

    @classmethod
    def create(
        cls, funcname: funcname, arguments: immutable_list[RRE_VALUE]
    ) -> RRE_THUNK:
        return cls(funcname, arguments, _sequence_depth_within_limits(arguments))


@dataclass(frozen=True)
class RRE_ERROR:
    msg: str


@dataclass(frozen=True)
class RRE_FORCE_THUNK:
    thunk: RRE_THUNK


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
class BindingLine:
    bind_name: str
    expr: Expr


@dataclass(frozen=True)
class FunctionDef:
    name: funcname
    modifiers: frozenset[FUNC_MODS]
    param_names: immutable_list[str]
    lines: immutable_list[BindingLine]


class FunctionMappingView(ImmutableMappingViewWithIdx[funcname, FunctionDef]):
    pass


@dataclass(frozen=True)
class Program:
    functions: FunctionMappingView


class RRE_TypeErrorException(Exception):
    def __init__(self, msg: str, *args: object) -> None:
        super().__init__(msg, *args)

        self.msg: str = msg


def clamp_int(value: int) -> RRE_INT:
    return RRE_INT(min(MAX_INT, max(MIN_INT, value)))


def _plus_exceeds_limits(
    container_len: int, container_depth: int, item: RRE_VALUE
) -> bool:
    if container_len + 1 > MAX_LIST_LENGTH:
        return True
    new_depth = max(container_depth, 1 + _item_nesting_depth(item))
    return new_depth > MAX_LIST_NESTING_DEPTH


def _plus_list(container: RRE_LIST, item: RRE_VALUE, *, prepend: bool) -> RRE_LIST:
    if _plus_exceeds_limits(len(container.value), container.depth, item):
        return container
    if prepend:
        return RRE_LIST.create(tuple([item]) + container.value)
    return RRE_LIST.create(container.value + tuple([item]))


def _plus_thunk(container: RRE_THUNK, item: RRE_VALUE, *, prepend: bool) -> RRE_THUNK:
    if _plus_exceeds_limits(len(container.arguments), container.depth, item):
        return container
    if prepend:
        return RRE_THUNK.create(container.funcname, tuple([item]) + container.arguments)
    return RRE_THUNK.create(container.funcname, container.arguments + tuple([item]))


def RRE_PLUS(val1: RRE_VALUE, val2: RRE_VALUE, _: FunctionMappingView) -> RRE_VALUE:
    match val1, val2:
        case RRE_INT(), RRE_INT():
            return clamp_int(val1.value + val2.value)
        case RRE_INT(), RRE_LIST():
            return _plus_list(val2, val1, prepend=True)
        case RRE_INT(), RRE_THUNK():
            return _plus_thunk(val2, val1, prepend=True)
        case RRE_INT(), RRE_ERROR():
            return val2
        #
        case RRE_LIST(), RRE_INT():
            return _plus_list(val1, val2, prepend=False)
        case RRE_LIST(), RRE_LIST():
            return _plus_list(val1, val2, prepend=False)
        case RRE_LIST(), RRE_THUNK():
            return _plus_list(val1, val2, prepend=False)
        case RRE_LIST(), RRE_ERROR():
            return val2
        #
        case RRE_THUNK(), RRE_INT():
            return _plus_thunk(val1, val2, prepend=False)
        case RRE_THUNK(), RRE_LIST():
            return _plus_thunk(val1, val2, prepend=False)
        case RRE_THUNK(), RRE_THUNK():
            return _plus_thunk(val1, val2, prepend=False)
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
            return RRE_ERROR(f"{val1.msg}+{val2.msg}")
        #
        case _:
            raise RRE_TypeErrorException("Unknown type in RRE_PLUS")


def lexicographical_comparison(
    lst1: immutable_list[RRE_VALUE],
    lst2: immutable_list[RRE_VALUE],
    functions: FunctionMappingView,
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
    functions: FunctionMappingView,
) -> int:
    match val1, val2:
        case RRE_INT(), RRE_INT():
            left_abs, right_abs = abs(val1.value), abs(val2.value)
            if left_abs != right_abs:
                return 1 if left_abs > right_abs else -1
            if val1.value == val2.value:
                return 0
            return -1 if val1.value < 0 else 1
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


def args_strictly_smaller(
    new_args: immutable_list[RRE_VALUE],
    old_args: immutable_list[RRE_VALUE],
    functions: FunctionMappingView,
) -> bool:
    return lexicographical_comparison(new_args, old_args, functions) < 0


def list_difference(
    list1: immutable_list[RRE_VALUE],
    list2: immutable_list[RRE_VALUE],
    functions: FunctionMappingView,
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
    val1: RRE_VALUE, val2: RRE_VALUE, functions: FunctionMappingView
) -> RRE_VALUE:
    match val1, val2:
        case RRE_INT(), RRE_INT():
            return clamp_int(val1.value - val2.value)
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
            return RRE_LIST.create(tuple(lst))
        case RRE_LIST(), RRE_LIST():
            return RRE_LIST.create(list_difference(val1.value, val2.value, functions))
        case RRE_LIST(), RRE_THUNK():
            return RRE_LIST.create(
                list_difference(val1.value, val2.arguments, functions)
            )
        case RRE_LIST(), RRE_ERROR():
            return val2
        #
        case RRE_THUNK(), RRE_INT():
            lst_idx = try_clamp_lst_idx(val2.value, len(val1.arguments))
            if lst_idx is None:
                return val1

            lst = list(val1.arguments)
            lst.pop(lst_idx)
            return RRE_THUNK.create(val1.funcname, tuple(lst))
        case RRE_THUNK(), RRE_LIST():
            return RRE_THUNK.create(
                val1.funcname, list_difference(val1.arguments, val2.value, functions)
            )
        case RRE_THUNK(), RRE_THUNK():
            return RRE_THUNK.create(
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
            return RRE_ERROR(f"{val1.msg}-{val2.msg}")
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
    val1: RRE_VALUE, val2: RRE_VALUE, functions: FunctionMappingView
) -> RRE_VALUE:
    if isinstance(val1, RRE_ERROR) and isinstance(val2, RRE_ERROR):
        return RRE_ERROR(f"{val1.msg}≥{val2.msg}")
    if isinstance(val1, RRE_ERROR):
        return val1
    if isinstance(val2, RRE_ERROR):
        return val2

    return RRE_INT(1) if value_comparison(val1, val2, functions) >= 0 else RRE_INT(0)


def RRE_CONDITION(
    val1: RRE_VALUE, val2: RRE_VALUE, _: FunctionMappingView
) -> RRE_VALUE | RRE_FORCE_THUNK:
    if is_truthy(val1):
        return val1

    if isinstance(val2, RRE_THUNK):
        return RRE_FORCE_THUNK(val2)

    return val2


EXPECTED_AMOUNT_OF_ARGS_IN_PRIMITIVE: int = 2
PrimitiveOpSignature: TypeAlias = Callable[
    [RRE_VALUE, RRE_VALUE, FunctionMappingView], RRE_VALUE | RRE_FORCE_THUNK
]


PRIMITIVE_OPS: dict[
    str,
    PrimitiveOpSignature,
] = {
    "+": RRE_PLUS,
    "-": RRE_MINUS,
    "?": RRE_CONDITION,
    "≥": RRE_COMPARE,
    ">": RRE_COMPARE,
}


@dataclass
class ExpressionStackFrame:
    expr: Expr
    caller_func: funcname
    bindings: ImmutableMappingViewWithIdx[str, RRE_VALUE]
    evaluated_args: list[RRE_VALUE] = field(default_factory=list)
    reduce_to_thunk: bool = False


MemoKey: TypeAlias = tuple[funcname, tuple[RRE_VALUE, ...]]


@dataclass
class FunctionStackFrame:
    funcname: funcname
    bindings: dict[str, RRE_VALUE] = field(default_factory=dict)
    current_line: int = 0
    memo_key: MemoKey | None = None
    prior_memo_keys: tuple[MemoKey, ...] = ()


@dataclass
class ForceFrame:
    value: RRE_VALUE
    memo_key: MemoKey | None = None
    prior_memo_keys: tuple[MemoKey, ...] = ()


CallStackFrame: TypeAlias = FunctionStackFrame | ExpressionStackFrame | ForceFrame


@dataclass
class ProgramStack:
    program: Program
    program_inputs: list[RRE_VALUE]
    call_stack: list[CallStackFrame] = field(default_factory=list)
    final_value: None | RRE_VALUE = None
    memo: dict[MemoKey, RRE_VALUE] = field(default_factory=dict)

    def copy_stack(self) -> ProgramStack:
        return ProgramStack(
            self.program,
            copy.deepcopy(self.program_inputs),
            copy.deepcopy(self.call_stack),
            self.final_value,
            copy.deepcopy(self.memo),
        )
