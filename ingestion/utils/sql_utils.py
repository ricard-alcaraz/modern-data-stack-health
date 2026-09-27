"""Helpers for building SQL safely from dynamic values."""
import re

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_QUALIFIED_PARTS = 3

def safe_identifier(name: str) -> str:
    """Validate a table/schema/column name before splicing it into SQL.

    Supports qualified names (e.g. 'raw.my_table' or 'db.raw.my_table')
    by validating every dot-separated segment independently.
    """
    parts = name.split(".")
    if not 1 <= len(parts) <= _MAX_QUALIFIED_PARTS:
        raise ValueError(f"Refusing to use unsafe SQL identifier: {name!r}")
    for part in parts:
        if not _IDENTIFIER_RE.match(part):
            raise ValueError(f"Refusing to use unsafe SQL identifier: {name!r}")
    return name


def quote_literal(value: str) -> str:
    """Escape a string for use as a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"