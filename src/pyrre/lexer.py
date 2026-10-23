import string

from pyrre.types import (
    Token,
    LexerError,
    TokenType,
    NAME_CHARS,
    QUOTE,
    SINGLE_CHAR_TOKENS,
)


def _try_commit_accumulated(
    accumulated: list[str], lexed: list[Token]
) -> None | LexerError:
    if not accumulated:
        return

    joined = "".join(accumulated)
    charset = set(accumulated)

    for tokentype in [
        TokenType.FUNCDEF,
        TokenType.ENDFUNCDEF,
        TokenType.CONSTEMPTYLST,
        TokenType.RETURN,
    ]:
        if joined == tokentype.value:
            lexed.append(Token(tokentype, tokentype.value))
            return

    if charset.issubset(string.digits):
        lexed.append(Token(TokenType.CONSTINT, joined))
        return

    if joined[0] in string.digits:
        return LexerError("Name can't start with digit")

    if not charset.issubset(NAME_CHARS):
        return LexerError("Name contains disallowed chars")

    lexed.append(Token(TokenType.NAME, joined))


def lex(text: str) -> list[Token] | LexerError:
    lexed: list[Token] = []
    accumulated: list[str] = []
    inside_quote: bool = False

    for char in text:
        if char == QUOTE:
            if inside_quote:
                lexed.append(Token(TokenType.CONSTSTR, "".join(accumulated)))
                accumulated = []
            inside_quote = not inside_quote
            continue

        if inside_quote:
            accumulated.append(char)
            continue

        if char in SINGLE_CHAR_TOKENS or char in string.whitespace:
            commission_error = _try_commit_accumulated(accumulated, lexed)
            if commission_error:
                return commission_error
            accumulated = []

            if char in SINGLE_CHAR_TOKENS:
                lexed.append(Token(SINGLE_CHAR_TOKENS[char], char))

            continue

        accumulated.append(char)

    if inside_quote:
        return LexerError("Unclosed quote at the end")

    commission_error = _try_commit_accumulated(accumulated, lexed)
    if commission_error:
        return commission_error

    return lexed + [Token(TokenType.EOF, TokenType.EOF.value)]
