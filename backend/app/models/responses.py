"""响应体模型"""

from pydantic import BaseModel


class DimensionScore(BaseModel):
    key: str
    name: str
    label: str
    score: int


class TalentReport(BaseModel):
    session_id: str
    test_type: str
    status: str
    dimensions: list[DimensionScore]
    summary: str


class SubmitResponse(BaseModel):
    session_id: str
    status: str
    dimensions: list[DimensionScore]
    summary: str


class DevReportResponse(BaseModel):
    session_id: str
    test_type: str
    dimensions: list[DimensionScore]
    summary: str
    ai_enhanced: bool = False
    cached: bool = False


class IntegrationEntry(BaseModel):
    status: str
    description: str
    endpoint: str | None = None
    url: str | None = None
    connected: bool | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    integrations: dict[str, IntegrationEntry]
