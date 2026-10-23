from types import MappingProxyType

from pyrre.types import (
    Token,
    TokenType,
    Program,
    FunctionDef,
    FUNC_MODS,
    ConstDef,
    Expr,
    RRE_INT,
    RRE_LIST,
    ParserErrorException,
    Var,
    Call,
    ParserError,
    PRIMITIVE_OPS,
    RRE_VALUE,
)
from pyrre.static_config import (
    MAX_CHAR_REPRESENTABLE_INT,
    MIN_CHAR_REPRESENTABLE_INT,
    MAX_INT,
    MIN_INT,
    MAX_LIST_LENGTH,
)


def parse_RRE_string(text: str) -> RRE_LIST:
    chars: list[RRE_VALUE] = []

    for char in text:
        if MIN_CHAR_REPRESENTABLE_INT > ord(char) > MAX_CHAR_REPRESENTABLE_INT:
            raise ParserErrorException(f"{char} is not allowed in a RRE string")

        if MIN_INT > ord(char) > MAX_INT:
            raise ParserErrorException(
                f"{char} is somehow out of the range for integers"
            )

        chars.append(RRE_INT(ord(char)))

    if len(chars) > MAX_LIST_LENGTH:
        raise ParserErrorException("string is too long")

    return RRE_LIST(chars)


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens: list[Token] = tokens
        self.pos: int = 0

    def current(self) -> Token:
        return self.tokens[self.pos]

    def match(self, expected: TokenType) -> None:
        if self.current().token_type == expected:
            self.pos += 1
        else:
            raise ParserErrorException(
                f"Expected {expected}, got {self.current().token_type}"
            )

    def parse(self) -> Program:
        return self._parse_funcs()

    def _parse_funcs(self) -> Program:
        funcs: dict[str, FunctionDef] = {}
        while True:
            if self.current().token_type == TokenType.EOF:
                self.match(TokenType.EOF)
                return Program(MappingProxyType(funcs))

            func = self._parse_func()
            if func.name in funcs:
                raise ParserErrorException(f"{func.name} defined more than once")

            funcs[func.name] = func

    def _parse_func(self) -> FunctionDef:
        self.match(TokenType.FUNCDEF)

        name = self.current().text
        self.match(TokenType.NAME)

        params = self._parse_params()
        mods = self._parse_func_mods()
        body = self._parse_until_endfunc()

        return FunctionDef(name, mods, params, *body)

    def _parse_params(self) -> list[str]:
        self.match(TokenType.LEFTPAR)

        params: list[str] = []

        while True:
            if self.current().token_type == TokenType.RIGHTPAR:
                self.match(TokenType.RIGHTPAR)
                return params

            name = self.current().text
            self.match(TokenType.NAME)
            params.append(name)
            if self.current().token_type == TokenType.COMMA:
                self.match(TokenType.COMMA)
            else:
                self.match(TokenType.RIGHTPAR)
                return params

    def _parse_func_mods(self) -> list[FUNC_MODS]:
        mods: list[FUNC_MODS] = []
        while True:
            if self.current().token_type != TokenType.FUNCMOD:
                return mods
            mods.append(FUNC_MODS(self.current().text))
            self.match(TokenType.FUNCMOD)

    def _parse_until_endfunc(self) -> tuple[list[ConstDef], Expr]:
        lines: list[ConstDef] = []

        while True:
            if self.current().token_type == TokenType.RETURN:
                self.match(TokenType.RETURN)
                return_expr = self._parse_expression()
                self.match(TokenType.ENDFUNCDEF)

                return lines, return_expr

            lines.append(self._parse_constant_line())

    def _parse_expression(self) -> Expr:
        text = self.current().text
        match self.current().token_type:
            case TokenType.CONSTINT:
                self.match(TokenType.CONSTINT)
                val = int(text)
                if MIN_INT > val > MAX_INT:
                    raise ParserErrorException(f"{text} is out of range for ints")
                return RRE_INT(int(text))
            case TokenType.CONSTEMPTYLST:
                self.match(TokenType.CONSTEMPTYLST)
                return RRE_LIST([])
            case TokenType.CONSTSTR:
                self.match(TokenType.CONSTSTR)
                return parse_RRE_string(text)
            case TokenType.NAME:
                self.match(TokenType.NAME)
                if self.current().token_type == TokenType.LEFTPAR:
                    return Call(text, self._parse_call_args())
                else:
                    return Var(text)

        raise ParserErrorException("Expected a constant or a subexpression")

    def _parse_call_args(self) -> list[Expr]:
        self.match(TokenType.LEFTPAR)
        if self.current().token_type == TokenType.RIGHTPAR:
            self.match(TokenType.RIGHTPAR)
            return []

        exprs: list[Expr] = []
        while True:
            exprs.append(self._parse_expression())
            if self.current().token_type == TokenType.COMMA:
                self.match(TokenType.COMMA)
            else:
                self.match(TokenType.RIGHTPAR)
                break

        return exprs

    def _parse_constant_line(self) -> ConstDef:
        constname = self.current().text
        self.match(TokenType.NAME)
        self.match(TokenType.EQUALS)
        return ConstDef(constname, self._parse_expression())


def _gather_func_call_names(
    item: Program | FunctionDef | Expr, func_calls: set[str]
) -> None:
    match item:
        case Program() as prog:
            for func in prog.functions.values():
                _gather_func_call_names(func, func_calls)
        case FunctionDef() as funcdef:
            for const in funcdef.lines:
                _gather_func_call_names(const.value, func_calls)
            _gather_func_call_names(funcdef.return_expr, func_calls)
        case Call() as call:
            func_calls.add(call.funcname)
            for param in call.params:
                _gather_func_call_names(param, func_calls)


def _check_calls_existing(program: Program) -> None:
    existing_funcs: set[str] = {c for c in PRIMITIVE_OPS}
    existing_funcs.update(func.name for func in program.functions.values())

    func_calls: set[str] = set()
    _gather_func_call_names(program, func_calls)

    if diff := (func_calls - existing_funcs):
        raise ParserErrorException(f"Some functions are called but not defined, {diff}")


def _check_unique_func_names_and_starting_letters(program: Program) -> None:
    starting_letters: set[str] = set()
    for func in program.functions.values():
        if func.name[0].lower() in starting_letters:
            raise ParserErrorException(
                f"function starting with {func.name[0]} defined more than once"
            )

        starting_letters.add(func.name[0].lower())


def _check_there_is_main(program: Program) -> None:
    for func in program.functions.values():
        if func.name.lower() == "main":
            return

    raise ParserErrorException("No main fnction among definitions")


def _post_parse_correctness(program: Program) -> Program:
    _check_there_is_main(program)
    _check_unique_func_names_and_starting_letters(program)
    _check_calls_existing(program)
    # TODO: check var names unique in a function
    return program


def parse(
    tokens: list[Token],
) -> (
    Program | ParserError
):  # TODO: remove ParserError, transition to exception handling
    parser = Parser(tokens)
    try:
        return _post_parse_correctness(parser.parse())
    except ParserErrorException as e:
        return ParserError(e.msg)
