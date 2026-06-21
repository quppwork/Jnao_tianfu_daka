"""请求体模型"""

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    answer: str = Field(..., min_length=35, max_length=35)
    uid: int
    type: int = Field(..., ge=0, le=1)
