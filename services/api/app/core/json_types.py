"""SQLAlchemy custom column type that validates JSON through a Pydantic model.

Usage:
    weather_snapshot: Mapped[WeatherSnapshot | None] = mapped_column(
        PydanticJSON(WeatherSnapshot)
    )
    colors: Mapped[list[ColorTag]] = mapped_column(
        PydanticJSON(list[ColorTag]), default=list
    )

Stored as a JSON value in the DB (JSONB on Postgres via dialect dispatch),
read back as the typed Python object.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class PydanticJSON(TypeDecorator[Any]):
    impl = JSON
    cache_ok = True

    def __init__(self, pydantic_type: Any) -> None:
        super().__init__()
        self._adapter: TypeAdapter[Any] = TypeAdapter(pydantic_type)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        return self._adapter.dump_python(value, mode="json")

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return self._adapter.validate_python(value)
