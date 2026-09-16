"""One centralized PostgreSQL identifier policy."""

import hashlib
import re
import unicodedata


POSTGRES_RESERVED_WORDS = frozenset({
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "asymmetric",
    "authorization", "binary", "both", "case", "cast", "check", "collate", "collation",
    "column", "concurrently", "constraint", "create", "cross", "current_catalog",
    "current_date", "current_role", "current_schema", "current_time", "current_timestamp",
    "current_user", "default", "deferrable", "desc", "distinct", "do", "else", "end",
    "except", "false", "fetch", "for", "foreign", "freeze", "from", "full", "grant",
    "group", "having", "ilike", "in", "initially", "inner", "intersect", "into", "is",
    "isnull", "join", "lateral", "leading", "left", "like", "limit", "localtime",
    "localtimestamp", "natural", "not", "notnull", "null", "offset", "on", "only", "or",
    "order", "outer", "overlaps", "placing", "primary", "references", "returning", "right",
    "select", "session_user", "similar", "some", "symmetric", "table", "tablesample", "then",
    "to", "trailing", "true", "union", "unique", "user", "using", "variadic", "verbose",
    "when", "where", "window", "with"
})


class PostgresIdentifierNormalizer:
    """Normalize and allocate collision-free identifiers within named scopes."""

    def __init__(self) -> None:
        self._used: dict[str, set[str]] = {}

    @staticmethod
    def _truncate(value: str, max_bytes: int = 63) -> str:
        raw = value.encode("utf-8")
        if len(raw) <= max_bytes:
            return value
        digest = hashlib.sha256(raw).hexdigest()[:8]
        budget = max_bytes - len(digest) - 1
        prefix = raw[:budget].decode("utf-8", errors="ignore").rstrip("_")
        return f"{prefix}_{digest}"

    @classmethod
    def canonical(cls, value: str) -> str:
        ascii_value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
        name = re.sub(r"[^a-z0-9_]+", "_", ascii_value.casefold()).strip("_")
        name = re.sub(r"_+", "_", name) or "unnamed"
        if not re.match(r"^[a-z_]", name):
            name = f"_{name}"
        if name in POSTGRES_RESERVED_WORDS:
            name = f"{name}_"
        return cls._truncate(name)

    def normalize(self, value: str, *, scope: str = "global") -> str:
        base = self.canonical(value)
        used = self._used.setdefault(scope, set())
        candidate, sequence = base, 2
        while candidate in used:
            suffix = f"_{sequence}"
            candidate = self._truncate(base, 63 - len(suffix.encode())) + suffix
            sequence += 1
        used.add(candidate)
        return candidate
