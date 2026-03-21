from typing import Literal, Optional

from pydantic import BaseModel, Field


BoardColumn = Literal["nao_postados", "a_postar", "programados", "postados"]
SubtitleFont = Literal["Arial", "Impact", "Georgia", "Tahoma", "Verdana"]
SubtitleColor = Literal["white", "yellow", "cyan", "green", "pink"]
CutStyle = Literal["viral", "engracado", "chocante", "informativo"]
ProcessSourceType = Literal["url", "local", "upload"]
PublishStatus = Literal["draft", "published", "failed"]


class ProcessRequest(BaseModel):
    creator_name: str = Field(min_length=2, max_length=100)
    source_type: Literal["url", "local"] = "url"
    source_value: str = Field(min_length=1)
    include_subtitles: bool = True
    subtitle_font: SubtitleFont = "Arial"
    subtitle_color: SubtitleColor = "yellow"
    cut_style: CutStyle = "viral"
    top_n: int = Field(default=5, ge=1, le=10)
    min_clip_seconds: int = Field(default=20, ge=10, le=120)
    max_clip_seconds: int = Field(default=50, ge=10, le=180)


class ClipItem(BaseModel):
    id: str
    job_id: Optional[str] = None
    creator_name: str
    source_type: Optional[ProcessSourceType] = None
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
    hashtags_text: str = ""
    notes: str = ""
    include_subtitles: bool = True
    subtitle_font: SubtitleFont = "Arial"
    subtitle_color: SubtitleColor = "yellow"
    cut_style: CutStyle = "viral"
    board_column: BoardColumn = "nao_postados"
    publish_status: PublishStatus = "draft"


class PublishRequest(BaseModel):
    clip_id: str
    mode: Literal["draft", "publish"] = "draft"


class ClipUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    caption: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    hashtags_text: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    board_column: Optional[BoardColumn] = None
    publish_status: Optional[PublishStatus] = None
