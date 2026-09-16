"""Database target boundary and safe local PostgreSQL implementation."""

from abc import ABC, abstractmethod
import os
import re
from typing import Any

from core.database_dry_run.models import DatabaseDryRunConfig

_SAFE_SCHEMA = re.compile(r"^dryrun_[a-z0-9_]{4,55}$")


def validate_dry_run_schema(schema: str, prefix: str = "dryrun_") -> None:
    if not schema.startswith(prefix) or not _SAFE_SCHEMA.fullmatch(schema):
        raise ValueError(f"Unsafe dry-run schema refused: {schema!r}")


class DatabaseTargetAdapter(ABC):
    @abstractmethod
    def connect(self) -> None: ...
    @abstractmethod
    def begin(self) -> None: ...
    @abstractmethod
    def commit(self) -> None: ...
    @abstractmethod
    def rollback(self) -> None: ...
    @abstractmethod
    def execute_ddl(self, sql: str) -> int: ...
    @abstractmethod
    def load_rows(self, schema: str, table: str, rows: list[dict[str, Any]], *, identity_column: str | None = None) -> list[dict[str, Any]]: ...
    @abstractmethod
    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]: ...
    @abstractmethod
    def inspect_schema(self, schema: str) -> dict[str, Any]: ...
    @abstractmethod
    def truncate_test_schema(self, schema: str) -> None: ...
    @abstractmethod
    def drop_test_schema(self, schema: str) -> None: ...
    @abstractmethod
    def close(self) -> None: ...


class PostgreSQLLocalAdapter(DatabaseTargetAdapter):
    """psycopg-backed adapter. Supabase/external targets are intentionally absent."""

    def __init__(self, config: DatabaseDryRunConfig):
        self.config, self.connection = config, None

    @staticmethod
    def driver_available() -> bool:
        try:
            import psycopg  # noqa: F401
            return True
        except ImportError:
            return False

    def connect(self) -> None:
        if self.config.host not in {"localhost", "127.0.0.1", "::1", "/var/run/postgresql"}:
            raise PermissionError("PostgreSQLLocalAdapter refuses non-local targets.")
        try: import psycopg
        except ImportError as error: raise ConnectionError("psycopg is not installed; PostgreSQL integration unavailable") from error
        password = self.config.password.get_secret_value() if self.config.password else os.getenv(self.config.password_env)
        self.connection = psycopg.connect(host=self.config.host, port=self.config.port,
            dbname=self.config.database, user=self.config.user, password=password,
            sslmode=self.config.ssl_mode, connect_timeout=max(1, self.config.statement_timeout // 1000))
        self.connection.execute("SELECT set_config('statement_timeout', %s, false)",
                                (str(self.config.statement_timeout),))
        self.connection.commit()

    def begin(self): self.connection.execute("BEGIN")
    def commit(self): self.connection.commit()
    def rollback(self): self.connection.rollback()
    def execute_ddl(self, sql):
        self.connection.execute(sql); return len([x for x in sql.split(";") if x.strip()])
    def load_rows(self, schema, table, rows, *, identity_column=None):
        validate_dry_run_schema(schema, self.config.test_schema_prefix)
        if not rows: return []
        from psycopg import sql
        catalog = self.query("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s",
                             (schema, table))
        known = {row["column_name"] for row in catalog}
        columns = [x for x in rows[0] if x != identity_column and x in known]
        statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
            sql.Identifier(schema), sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns)),
            sql.SQL(",").join(sql.Placeholder() for _ in columns))
        if identity_column: statement += sql.SQL(" RETURNING {} ").format(sql.Identifier(identity_column))
        result=[]
        for row in rows:
            cursor=self.connection.execute(statement, tuple(row.get(c) for c in columns))
            result.append({**row, **({identity_column: cursor.fetchone()[0]} if identity_column else {})})
        return result
    def query(self, sql, params=()):
        cursor=self.connection.execute(sql, params)
        names=[x.name for x in cursor.description] if cursor.description else []
        return [dict(zip(names,row)) for row in cursor.fetchall()] if names else []
    def inspect_schema(self, schema):
        rows=self.query("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema=%s ORDER BY table_name,ordinal_position",(schema,))
        tables={}
        for row in rows: tables.setdefault(row["table_name"],{"columns":{}})["columns"][row["column_name"]]=row
        return {"tables":tables}
    def truncate_test_schema(self, schema):
        validate_dry_run_schema(schema, self.config.test_schema_prefix)
        from psycopg import sql
        for table in self.inspect_schema(schema)["tables"]:
            self.connection.execute(sql.SQL("TRUNCATE {}.{} CASCADE").format(sql.Identifier(schema),sql.Identifier(table)))
    def drop_test_schema(self, schema):
        validate_dry_run_schema(schema, self.config.test_schema_prefix)
        from psycopg import sql
        self.connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
    def close(self):
        if self.connection: self.connection.close(); self.connection=None


class InMemoryDatabaseTargetAdapter(DatabaseTargetAdapter):
    """Controlled relational test double with transactions and independent identities."""
    def __init__(self, schema_plan=None):
        self.plan=schema_plan; self.schemas={}; self._snapshot=None; self.connected=False
    def connect(self): self.connected=True
    def begin(self):
        import copy; self._snapshot=copy.deepcopy(self.schemas)
    def commit(self): self._snapshot=None
    def rollback(self):
        if self._snapshot is not None: self.schemas=self._snapshot; self._snapshot=None
    def execute_ddl(self, sql):
        schema=self.plan.target_schema
        self.schemas[schema]={t.physical_name:{"rows":[],"table":t,"next_identity":1001} for t in self.plan.tables}
        return len([x for x in sql.split(";") if x.strip()])
    def load_rows(self,schema,table,rows,*,identity_column=None):
        target=self.schemas[schema][table]; output=[]
        known={c.physical_name for c in target["table"].columns}
        for original in rows:
            row={k:v for k,v in original.items() if k in known}
            if identity_column:
                row[identity_column]=target["next_identity"]; target["next_identity"]+=1
            for col in target["table"].columns:
                if not col.nullable and "GENERATED" not in col.postgres_type and row.get(col.physical_name) is None:
                    raise ValueError(f"NOT NULL violation: {table}.{col.physical_name}")
            pk=target["table"].primary_key
            if pk and any(all(old.get(c)==row.get(c) for c in pk.columns) for old in target["rows"]):
                raise ValueError(f"PK violation: {table}")
            for uq in target["table"].unique_constraints:
                if any(all(old.get(c)==row.get(c) for c in uq.columns) for old in target["rows"]): raise ValueError(f"UNIQUE violation: {table}")
            target["rows"].append(row); output.append(dict(row))
        return output
    def query(self,sql,params=()): return []
    def inspect_schema(self,schema):
        return {"tables":{name:{"columns":{c.physical_name:{"data_type":c.postgres_type,"is_nullable":"YES" if c.nullable else "NO"} for c in item["table"].columns},"table":item["table"],"rows":list(item["rows"])} for name,item in self.schemas.get(schema,{}).items()}}
    def truncate_test_schema(self,schema):
        validate_dry_run_schema(schema)
        for item in self.schemas[schema].values(): item["rows"].clear()
    def drop_test_schema(self,schema): validate_dry_run_schema(schema); self.schemas.pop(schema,None)
    def close(self): self.connected=False
