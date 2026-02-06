"""ULID generation utilities"""

from ulid import ULID


def ulid() -> str:
    """Generate a ULID (Universally Unique Lexicographically Sortable Identifier)

    Returns:
        String representation of ULID
    """
    return str(ULID())
