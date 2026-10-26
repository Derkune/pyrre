import string

from pyrre.types import (
    Token,
    TokenType,
    NAME_CHARS,
    QUOTE,
    SINGLE_CHAR_TOKENS,
    LexerErrorException,
)
from pyrre.static_config import MAX_INT, MAX_LIST_LENGTH


def _try_commit_accumulated(accumulated: list[str], lexed: list[Token]) -> None:
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
        if int(joined) > MAX_INT:
            raise LexerErrorException(f"{joined} is out of range for ints")
        lexed.append(Token(TokenType.CONSTINT, joined))
        return

    if joined[0] in string.digits:
        raise LexerErrorException("Name can't start with digit")

    if joined[0] not in string.ascii_letters:
        raise LexerErrorException("Name must start with a letter")

    if not charset.issubset(NAME_CHARS):
        raise LexerErrorException("Name contains disallowed chars")

    lexed.append(Token(TokenType.NAME, joined))


def lex(text: str) -> list[Token]:
    lexed: list[Token] = []
    accumulated: list[str] = []
    inside_quote: bool = False
    skip_next: bool = False

    for i, char in enumerate(text):
        if skip_next:
            skip_next = False
            continue
        if inside_quote:
            if char == "\\" and i + 1 < len(text) and text[i + 1] == QUOTE:
                accumulated.append(QUOTE)
                skip_next = True
                continue
            if char == QUOTE:
                joined = "".join(accumulated)
                if len(joined) > MAX_LIST_LENGTH:
                    raise LexerErrorException("string is too long")
                lexed.append(Token(TokenType.CONSTSTR, joined))
                accumulated = []
                inside_quote = False
                continue
            accumulated.append(char)
            continue

        if char == QUOTE:
            inside_quote = True
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
        raise LexerErrorException("Unclosed quote at the end")

    commission_error = _try_commit_accumulated(accumulated, lexed)
    if commission_error:
        return commission_error

    return lexed + [Token(TokenType.EOF, TokenType.EOF.value)]
