"""Lightweight structural validation without a database connection."""

import re
from pydantic import BaseModel, Field

from core.ddl.identifiers import PostgresIdentifierNormalizer
from core.ddl.models import PhysicalSchemaPlan


class DDLValidationResult(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)


def validate_postgresql_ddl(sql: str, plan: PhysicalSchemaPlan) -> DDLValidationResult:
    errors: list[str] = []
    upper = sql.upper()
    for forbidden in ("DROP ", "TRUNCATE ", "DELETE ", "ALTER "):
        if forbidden in upper:
            errors.append(f"Destructive/unsupported statement found: {forbidden.strip()}")
    if sql.count("(") != sql.count(")"):
        errors.append("Unbalanced parentheses.")
    if not sql.endswith(";\n") or any(not part.strip() for part in sql.split(";")[:-1]):
        errors.append("Invalid statement boundaries.")
    tables = {table.physical_name: table for table in plan.tables}
    if len(tables) != len(plan.tables): errors.append("Duplicate table names.")
    objects = set()
    for table in plan.tables:
        if PostgresIdentifierNormalizer.canonical(table.physical_name) != table.physical_name:
            errors.append(f"Invalid table identifier: {table.physical_name}")
        columns = {column.physical_name for column in table.columns}
        if len(columns) != len(table.columns): errors.append(f"Duplicate columns in {table.physical_name}.")
        for constraint in ([table.primary_key] if table.primary_key else []) + table.unique_constraints + table.check_constraints + table.foreign_keys:
            if constraint.name in objects: errors.append(f"Duplicate constraint: {constraint.name}")
            objects.add(constraint.name)
            if not set(constraint.columns) <= columns: errors.append(f"Invalid columns in {constraint.name}")
            if constraint.referenced_table:
                target = tables.get(constraint.referenced_table)
                if not target: errors.append(f"Missing referenced table: {constraint.referenced_table}")
                elif not set(constraint.referenced_columns) <= {c.physical_name for c in target.columns}:
                    errors.append(f"Missing referenced columns in {constraint.name}")
    for index in plan.indexes:
        table = tables.get(index.table_name)
        if index.name in objects: errors.append(f"Duplicate object: {index.name}")
        objects.add(index.name)
        if not table or not set(index.columns) <= {c.physical_name for c in table.columns}:
            errors.append(f"Invalid index: {index.name}")
    if re.search(r'"', sql): errors.append("Quoted identifiers are outside the normalized identifier policy.")
    return DDLValidationResult(passed=not errors, errors=errors)
