import enum
from dataclasses import dataclass
import string
from typing import Generator

from pyrre import main


OMMITTED_ARG: str = "_"
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
PRIMITIVE_OPS: str = "+-?≥" + ">"  # alias
QUOTE = '"'


class TokenType(enum.Enum):
    FUNCDEF = "func"
    NAME = "NAME"
    ENDFUNCDEF = "endfunc"
    LEFTPAR = "("
    RIGHTPAR = ")"
    FUNCMOD = "!@#%"
    COMMA = ","
    CONSTINT = string.digits
    CONSTEMPTYLST = "[]"
    CONSTSTR = "CONSTSTR"
    EQUALS = "="


SINGLE_CHAR_TOKENS: dict[str, TokenType] = dict(
    [
        (TokenType.LEFTPAR.value, TokenType.LEFTPAR),
        (TokenType.RIGHTPAR.value, TokenType.RIGHTPAR),
        (TokenType.COMMA.value, TokenType.COMMA),
        (TokenType.EQUALS.value, TokenType.EQUALS),
    ]
    + [(char, TokenType.FUNCMOD) for char in TokenType.FUNCMOD.value]
    + [(char, TokenType.NAME) for char in PRIMITIVE_OPS + OMMITTED_ARG]
)


@dataclass
class Token:
    token_type: TokenType
    text: str

    def __repr__(self) -> str:
        return f'{self.token_type.name}: "{self.text}"'


@dataclass
class LexerError:
    msg: str


def try_commit_accumulated(
    accumulated: list[str], lexed: list[Token]
) -> None | LexerError:
    if not accumulated:
        return

    joined = "".join(accumulated)
    charset = set(accumulated)

    for tokentype in [TokenType.FUNCDEF, TokenType.ENDFUNCDEF, TokenType.CONSTEMPTYLST]:
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
            commission_error = try_commit_accumulated(accumulated, lexed)
            if commission_error:
                return commission_error
            accumulated = []

            if char in SINGLE_CHAR_TOKENS:
                lexed.append(Token(SINGLE_CHAR_TOKENS[char], char))

            continue

        accumulated.append(char)

    if inside_quote:
        return LexerError("Unclosed quote at the end")

    commission_error = try_commit_accumulated(accumulated, lexed)
    if commission_error:
        return commission_error

    return lexed


if __name__ == "__main__":
    with open("testprogram.rre", "r", encoding="utf-8") as _f:
        lexed = lex(_f.read())
        pass
