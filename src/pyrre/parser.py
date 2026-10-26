from typing import Iterator

from pyrre.types import (
    Token,
    TokenType,
    Program,
    FunctionDef,
    FUNC_MODS,
    BindingLine,
    Expr,
    RRE_INT,
    RRE_LIST,
    RRE_ERROR,
    ERROR_CONST_SYMBOL,
    ParserErrorException,
    Binding,
    Call,
    PRIMITIVE_OPS,
    RRE_VALUE,
    funcname,
    ImmutableMappingViewWithIdx,
    immutable_list,
    RETURN_BINDING,
    PrimitiveOpSignature,
    FunctionMappingView,
)
from pyrre.static_config import (
    MAX_CHAR_REPRESENTABLE_INT,
    MIN_CHAR_REPRESENTABLE_INT,
    MAX_INT,
    MIN_INT,
    MAX_LIST_LENGTH,
    MAX_ARGS,
)


def finite_while(i: int = 100000) -> Iterator[None]:
    for _ in range(i):
        yield

    raise Exception("went to the limit in finite_while")


def parse_RRE_string(text: str) -> RRE_LIST:
    chars: list[RRE_VALUE] = []

    for char in text:
        if (
            MIN_CHAR_REPRESENTABLE_INT > ord(char)
            or ord(char) > MAX_CHAR_REPRESENTABLE_INT
        ):
            raise ParserErrorException(f"{char} is not allowed in an RRE string")

        if MIN_INT > ord(char) or ord(char) > MAX_INT:
            raise ParserErrorException(
                f"{char} is somehow out of the range for integers"
            )

        chars.append(RRE_INT(ord(char)))

    if len(chars) > MAX_LIST_LENGTH:
        raise ParserErrorException("string is too long")

    return RRE_LIST.create(tuple(chars))


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
        funcs: dict[funcname, FunctionDef] = {}
        for _ in finite_while():
            if self.current().token_type == TokenType.EOF:
                self.match(TokenType.EOF)
                return Program(FunctionMappingView(funcs))

            func = self._parse_func()
            if func.name in funcs:
                raise ParserErrorException(f"{func.name} defined more than once")

            funcs[func.name] = func

        raise ParserErrorException("Went over finite iteration limit")

    def _parse_func(self) -> FunctionDef:
        self.match(TokenType.FUNCDEF)

        name = self.current().text
        self.match(TokenType.NAME)

        params = self._parse_params()
        mods = self._parse_func_mods()
        lines = self._parse_until_endfunc()

        return FunctionDef(name, mods, params, lines)

    def _parse_params(self) -> immutable_list[str]:
        self.match(TokenType.LEFTPAR)

        params: list[str] = []

        for _ in finite_while():
            if self.current().token_type == TokenType.RIGHTPAR:
                self.match(TokenType.RIGHTPAR)
                return tuple(params)

            name = self.current().text
            self.match(TokenType.NAME)
            params.append(name)
            if len(params) > MAX_ARGS:
                raise ParserErrorException("too many function parameters")
            if self.current().token_type == TokenType.COMMA:
                self.match(TokenType.COMMA)
            else:
                self.match(TokenType.RIGHTPAR)
                return tuple(params)

        raise ParserErrorException("Went over finite iteration limit")

    def _parse_func_mods(self) -> frozenset[FUNC_MODS]:
        mods: list[FUNC_MODS] = []
        for _ in finite_while():
            if self.current().token_type != TokenType.FUNCMOD:
                return frozenset(mods)
            mods.append(FUNC_MODS(self.current().text))
            self.match(TokenType.FUNCMOD)

        raise ParserErrorException("Went over finite iteration limit")

    def _parse_until_endfunc(self) -> immutable_list[BindingLine]:
        lines: list[BindingLine] = []

        for _ in finite_while():
            if self.current().token_type == TokenType.RETURN:
                self.match(TokenType.RETURN)
                return_expr = self._parse_expression()
                self.match(TokenType.ENDFUNCDEF)

                return tuple(lines + [BindingLine(RETURN_BINDING, return_expr)])

            lines.append(self._parse_expr_line())

        raise ParserErrorException("Went over finite iteration limit")

    def _parse_expression(self) -> Expr:
        text = self.current().text
        match self.current().token_type:
            case TokenType.CONSTINT:
                self.match(TokenType.CONSTINT)
                val = int(text)
                if val < MIN_INT or val > MAX_INT:
                    raise ParserErrorException(f"{text} is out of range for ints")
                return RRE_INT(val)
            case TokenType.CONSTEMPTYLST:
                self.match(TokenType.CONSTEMPTYLST)
                return RRE_LIST.create(tuple())
            case TokenType.CONSTSTR:
                self.match(TokenType.CONSTSTR)
                return parse_RRE_string(text)
            case TokenType.NAME:
                self.match(TokenType.NAME)
                if text == ERROR_CONST_SYMBOL:
                    return self._parse_error_constant()
                if self.current().token_type == TokenType.LEFTPAR:
                    return Call(text, self._parse_call_args())
                else:
                    return Binding(text)

        raise ParserErrorException("Expected a constant or a subexpression")

    def _parse_call_args(self) -> immutable_list[Expr]:
        self.match(TokenType.LEFTPAR)
        if self.current().token_type == TokenType.RIGHTPAR:
            self.match(TokenType.RIGHTPAR)
            return tuple()

        exprs: list[Expr] = []
        for _ in finite_while():
            exprs.append(self._parse_expression())
            if len(exprs) > MAX_ARGS:
                raise ParserErrorException("too many call arguments")
            if self.current().token_type == TokenType.COMMA:
                self.match(TokenType.COMMA)
            else:
                self.match(TokenType.RIGHTPAR)
                break

        return tuple(exprs)

    def _parse_error_constant(self) -> RRE_ERROR:
        self.match(TokenType.LEFTPAR)
        if self.current().token_type != TokenType.CONSTSTR:
            raise ParserErrorException(
                "Error constant ~ requires a single string argument"
            )
        text = self.current().text
        self.match(TokenType.CONSTSTR)
        parse_RRE_string(text)
        self.match(TokenType.RIGHTPAR)
        return RRE_ERROR(text)

    def _parse_expr_line(self) -> BindingLine:
        constname = self.current().text
        self.match(TokenType.NAME)
        self.match(TokenType.EQUALS)
        return BindingLine(constname, self._parse_expression())


def _check_main_is_not_lazy(program: Program) -> None:
    main = _find_main(program)
    assert main is not None
    main_func = program.functions[main]

    if FUNC_MODS.NON_EAGER in main_func.modifiers:
        raise ParserErrorException("main can't be lazy")


def _gather_binds_referenced_in_expr(expr: Expr) -> set[str]:
    match expr:
        case Binding() as bind:
            return set([bind.bindname])
        case Call() as call:
            s = set()
            for call_expr in call.params:
                s.update(_gather_binds_referenced_in_expr(call_expr))
            return s
        case _:
            return set()


def _check_references_existing_binds(program: Program) -> None:
    for func in program.functions.values():
        funcbinds = set(func.param_names)
        for line in func.lines:
            binds_referenced = _gather_binds_referenced_in_expr(line.expr)

            if binds_referenced.difference(funcbinds):
                raise ParserErrorException("referencing an undefined binding")

            if not isinstance(line, BindingLine):
                continue

            funcbinds.add(line.bind_name)


def _check_unique_exprs(program: Program) -> None:
    for func in program.functions.values():
        params = set(func.param_names)
        if len(params) != len(func.param_names):
            raise ParserErrorException("Non-unique func param names")

        lines = set(l.bind_name for l in func.lines if isinstance(l, BindingLine))
        if len(lines) != len(func.lines):
            raise ParserErrorException("Non-unique func binding names")

        allbinds = params.union(lines)
        if len(allbinds) != len(lines) + len(params):
            raise ParserErrorException("Overlap between param names and binding names")


def _gather_func_call_names(
    item: Program | FunctionDef | Expr, func_calls: set[str]
) -> None:
    match item:
        case Program() as prog:
            for func in prog.functions.values():
                _gather_func_call_names(func, func_calls)
        case FunctionDef() as funcdef:
            for line in funcdef.lines:
                _gather_func_call_names(line.expr, func_calls)
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


def _find_main(program: Program) -> None | str:
    for func in program.functions.values():
        if func.name.lower() == "main":
            return func.name

    return None


def _check_there_is_main(program: Program) -> None:
    if _find_main(program) is not None:
        return

    raise ParserErrorException("No main function among definitions")


def _gather_self_calls(expr: Expr, name: funcname, acc: list[Call]) -> None:
    match expr:
        case Call() as call:
            if call.funcname == name:
                acc.append(call)
            for param in call.params:
                _gather_self_calls(param, name, acc)


def _tail_self_call(expr: Expr, name: funcname) -> Call | None:
    match expr:
        case Call() as call:
            if call.funcname == "?":
                if len(call.params) != 2:
                    return None
                return _tail_self_call(call.params[1], name)
            if call.funcname == name:
                return call
            return None
        case _:
            return None


def _check_tail_recursion(program: Program) -> None:
    for func in program.functions.values():
        if FUNC_MODS.TAIL_RECURSE not in func.modifiers:
            continue

        self_calls: list[Call] = []
        for line in func.lines:
            _gather_self_calls(line.expr, func.name, self_calls)

        return_expr = func.lines[-1].expr
        allowed = _tail_self_call(return_expr, func.name)
        if any(call is not allowed for call in self_calls):
            raise ParserErrorException(
                "tail-recursive call must be the return statement"
            )


def _post_parse_correctness(program: Program) -> Program:
    _check_there_is_main(program)
    _check_unique_func_names_and_starting_letters(program)
    _check_calls_existing(program)
    _check_unique_exprs(program)
    _check_references_existing_binds(program)
    _check_main_is_not_lazy(program)
    _check_tail_recursion(program)
    return program


def parse(
    tokens: list[Token],
) -> Program:
    parser = Parser(tokens)
    return _post_parse_correctness(parser.parse())
