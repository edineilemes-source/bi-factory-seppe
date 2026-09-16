"""Artifact-backed business intelligence MVP for validated source-record grain."""

from core.bi_mvp.modeling import build_mvp_model
from core.bi_mvp.ddl import generate_postgresql_ddl
from core.bi_mvp.etl import load_postgresql

__all__ = ["build_mvp_model", "generate_postgresql_ddl", "load_postgresql"]
