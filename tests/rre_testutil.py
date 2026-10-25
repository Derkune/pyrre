import re

_FUNC_HEADER = re.compile(
    r"(func\s+[A-Za-z][A-Za-z0-9_]*\s*\([^)]*\))(\s*[!@#%]*)"
)


def apply_memoize_modifier(code: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix, mods = match.group(1), match.group(2)
        if "#" in mods:
            return match.group(0)
        return prefix + mods + "#"

    return _FUNC_HEADER.sub(repl, code)
