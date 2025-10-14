from __future__ import annotations
# ruff: noqa: I001

from pydantic import BaseModel, Field

class Prediction(BaseModel):
    id: str
    label: str
    path: list[str]
    score: float = Field(ge=0, le=1)
    method: str

class Alternative(BaseModel):
    id: str
    label: str
    score: float = Field(ge=0, le=1)

class ClassifyRequest(BaseModel):
    query: str
    top_k: int | None = 5
    lang: str | None = "es"   # <-- requerido por /classify

class ClassifyResponse(BaseModel):
    prediction: Prediction | None
    alternatives: list[Alternative]
    abstained: bool
    latency_ms: int

class TaxoResult(BaseModel):
    id: str
    label: str
    path: list[str]

class TaxoSearchResponse(BaseModel):
    results: list[TaxoResult]

class AutocompleteResult(BaseModel):
    id: str
    label: str
    kind: str  # pref | alt

class AutocompleteResponse(BaseModel):
    results: list[AutocompleteResult]

class TaxoConceptDetail(BaseModel):
    id: str
    uri: str | None = None
    pref_label: dict[str, str] = Field(alias="prefLabel")
    alt_label: dict[str, list[str]] = Field(alias="altLabel")
    hidden_label: dict[str, list[str]] = Field(alias="hiddenLabel")
    definition: dict[str, str | None]
    scope_note: dict[str, str | None] = Field(alias="scopeNote")
    note: dict[str, str | None]
    example: dict[str, list[str]]
    path: dict[str, list[str]]
    broader: list[str]
    narrower: list[str]
    exact_match: list[str] = Field(alias="exactMatch")
    close_match: list[str] = Field(alias="closeMatch")
    related: list[str]

    class Config:
        allow_population_by_field_name = True

class FeedbackRequest(BaseModel):
    query: str
    predicted_id: str | None = None
    correct_id: str | None = None
