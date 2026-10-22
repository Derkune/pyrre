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
)


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
        funcs: list[FunctionDef] = []
        while True:
            if self.current().token_type == TokenType.EOF:
                self.match(TokenType.EOF)
                return Program(funcs)

            funcs.append(self._parse_func())

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
        constants: list[ConstDef] = []

        while True:
            if self.current().token_type == TokenType.RETURN:
                self.match(TokenType.RETURN)
                return_expr = self._parse_expression()
                self.match(TokenType.ENDFUNCDEF)

                return constants, return_expr

            constants.append(self._parse_constant_line())

    def _parse_expression(self) -> Expr:
        text = self.current().text
        match self.current().token_type:
            case TokenType.CONSTINT:
                self.match(TokenType.CONSTINT)
                return RRE_INT(int(text))
            case TokenType.CONSTEMPTYLST:
                self.match(TokenType.CONSTEMPTYLST)
                return RRE_LIST([])
            case TokenType.CONSTSTR:
                self.match(TokenType.CONSTSTR)
                return RRE_LIST([RRE_INT(999)] * 9)
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


def gather_func_call_names(
    item: Program | FunctionDef | Expr, func_calls: set[str]
) -> None:
    match item:
        case Program() as prog:
            for func in prog.functions:
                gather_func_call_names(func, func_calls)
        case FunctionDef() as funcdef:
            for const in funcdef.constants:
                gather_func_call_names(const.value, func_calls)
            gather_func_call_names(funcdef.return_expr, func_calls)
        case Call() as call:
            func_calls.add(call.funcname)
            for param in call.params:
                gather_func_call_names(param, func_calls)


def check_calls_existing(program: Program) -> None:
    existing_funcs: set[str] = {c for c in PRIMITIVE_OPS}
    existing_funcs.update(func.name for func in program.functions)

    func_calls: set[str] = set()
    gather_func_call_names(program, func_calls)

    if diff := (func_calls - existing_funcs):
        raise ParserErrorException(f"Some functions are called but not defined, {diff}")


def check_unique_func_names_and_starting_letters(program: Program) -> None:
    names: set[str] = set()
    starting_letters: set[str] = set()
    for func in program.functions:
        if func.name.lower() in names:
            raise ParserErrorException(f"{func.name} defined more than 1 time")
        if func.name[0].lower() in starting_letters:
            raise ParserErrorException(
                f"function starting with {func.name[0]} defined more than once"
            )

        names.add(func.name.lower())
        starting_letters.add(func.name[0].lower())


def check_there_is_main(program: Program) -> None:
    for func in program.functions:
        if func.name.lower() == "main":
            return

    raise ParserErrorException("No main fnction among definitions")


def post_parse_correctness(program: Program) -> Program:
    check_there_is_main(program)
    check_unique_func_names_and_starting_letters(program)
    check_calls_existing(program)
    return program


def parse(tokens: list[Token]) -> Program | ParserError:
    parser = Parser(tokens)
    try:
        return post_parse_correctness(parser.parse())
    except ParserErrorException as e:
        return ParserError(e.msg)
