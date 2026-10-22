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

    # grammar definition below

    def parse(self) -> Program:
        funcs: list[FunctionDef] = []
        while True:
            if self.current().token_type == TokenType.EOF:
                return Program(funcs)

            funcs.append(self.parse_func())

    def parse_func(self) -> FunctionDef:
        self.match(TokenType.FUNCDEF)

        name = self.current().text
        self.match(TokenType.NAME)

        params = self.parse_params()
        mods = self.parse_func_mods()
        body = self.parse_until_endfunc()

        return FunctionDef(name, mods, params, *body)

    def parse_params(self) -> list[str]:
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

    def parse_func_mods(self) -> list[FUNC_MODS]:
        mods: list[FUNC_MODS] = []
        while True:
            if self.current().token_type != TokenType.FUNCMOD:
                return mods
            mods.append(FUNC_MODS(self.current().text))
            self.match(TokenType.FUNCMOD)

    def parse_until_endfunc(self) -> tuple[list[ConstDef], Expr]:
        constants: list[ConstDef] = []

        while True:
            if self.current().token_type == TokenType.RETURN:
                self.match(TokenType.RETURN)
                return_expr = self.parse_expression()
                self.match(TokenType.ENDFUNCDEF)

                return constants, return_expr

            constants.append(self.parse_constant_line())

    def parse_expression(self) -> Expr:
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
                    return Call(text, self.parse_call_args())
                else:
                    return Var(text)

        raise ParserErrorException("Expected a constant or a subexpression")

    def parse_call_args(self) -> list[Expr]:
        self.match(TokenType.LEFTPAR)
        if self.current().token_type == TokenType.RIGHTPAR:
            self.match(TokenType.RIGHTPAR)
            return []

        exprs: list[Expr] = []
        while True:
            exprs.append(self.parse_expression())
            if self.current().token_type == TokenType.COMMA:
                self.match(TokenType.COMMA)
            else:
                self.match(TokenType.RIGHTPAR)
                break

        return exprs

    def parse_constant_line(self) -> ConstDef:
        constname = self.current().text
        self.match(TokenType.NAME)
        self.match(TokenType.EQUALS)
        return ConstDef(constname, self.parse_expression())


def parse(tokens: list[Token]) -> Program | ParserError:
    parser = Parser(tokens)
    try:
        return parser.parse()
    except ParserErrorException as e:
        return ParserError(e.msg)
