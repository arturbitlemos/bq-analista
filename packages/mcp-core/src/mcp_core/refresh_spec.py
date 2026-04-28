from __future__ import annotations
from datetime import date
from pydantic import BaseModel, model_validator, Field


class RefreshQuery(BaseModel):
    id: str = Field(min_length=1)
    sql: str = Field(min_length=1)

    def render(self, *, start: date, end: date) -> str:
        return self.sql.replace("{{start_date}}", start.isoformat()).replace("{{end_date}}", end.isoformat())


class DataBlockRef(BaseModel):
    block_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)


class PeriodRange(BaseModel):
    start: date
    end: date


class RefreshSpec(BaseModel):
    queries: list[RefreshQuery]
    data_blocks: list[DataBlockRef]
    original_period: PeriodRange

    @model_validator(mode="after")
    def _validate(self) -> "RefreshSpec":
        # Unique query ids
        ids = [q.id for q in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate query id in queries[]")

        # Each query SQL must have both placeholders
        for q in self.queries:
            if "{{start_date}}" not in q.sql or "{{end_date}}" not in q.sql:
                raise ValueError(f"query {q.id!r}: missing placeholder {{start_date}} or {{end_date}}")

        # Each data_block.query_id must reference an existing query
        valid_ids = set(ids)
        for db in self.data_blocks:
            if db.query_id not in valid_ids:
                raise ValueError(f"data_block {db.block_id!r} references unknown query_id {db.query_id!r}")

        return self
