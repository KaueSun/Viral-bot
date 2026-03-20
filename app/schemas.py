from pydantic import BaseModel, Field
from typing import Literal, Optional


class ProcessRequest(BaseModel):
    creator_name: str = Field(min_length=2, max_length=100)
    source_type: Literal["url", "local"] = "url"
    source_value: str = Field(min_length=1)
    top_n: int = Field(default=5, ge=1, le=10)
    min_clip_seconds: int = Field(default=20, ge=10, le=120)
    max_clip_seconds: int = Field(default=50, ge=10, le=180)


class ClipItem(BaseModel):
    id: str
    creator_name: str
    source_title: str
    source_path: str
    clip_path: str
    subtitle_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    score: float
    title: str
    caption: str
    publish_status: Literal["draft", "published", "failed"] = "draft"


class PublishRequest(BaseModel):
    clip_id: str
    mode: Literal["draft", "publish"] = "draft"