from __future__ import annotations
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class RefreshQuery(BaseModel):
    id: str = Field(min_length=1)
    sql: str = Field(min_length=1)

    def render(self, *, start: date, end: date) -> str:
        return self.sql.replace("{{start_date}}", start.isoformat()).replace("{{end_date}}", end.isoformat())


class DataBlockSchema(BaseModel):
    """Declares the shape a refreshed payload must have before being written
    into a `<script id=...>` block. `shape="array"` means the BQ rows go in
    as-is; `shape="object"` means the query MUST return exactly one row, and
    that row is unwrapped (so the JS sees an object, not a 1-element array)."""
    shape: Literal["array", "object"] = "array"
    fields: list[str] = Field(min_length=1)


class DataBlockRef(BaseModel):
    block_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    # Aliased to `schema` in the JSON because Pydantic's `BaseModel.schema`
    # method shadows attribute access. Using `schema_` avoids the collision
    # while keeping the wire format intuitive.
    schema_: DataBlockSchema | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


class PeriodRange(BaseModel):
    start: date
    end: date


class RefreshSpec(BaseModel):
    queries: list[RefreshQuery]
    data_blocks: list[DataBlockRef]
    original_period: PeriodRange

    @model_validator(mode="after")
    def _validate(self) -> "RefreshSpec":
        ids = [q.id for q in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate query id in queries[]")

        for q in self.queries:
            if "{{start_date}}" not in q.sql or "{{end_date}}" not in q.sql:
                raise ValueError(f"query {q.id!r}: missing placeholder {{start_date}} or {{end_date}}")

        valid_ids = set(ids)
        for db_ref in self.data_blocks:
            if db_ref.query_id not in valid_ids:
                raise ValueError(f"data_block {db_ref.block_id!r} references unknown query_id {db_ref.query_id!r}")

        return self
