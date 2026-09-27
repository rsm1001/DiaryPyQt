"""日记 API 请求和响应模型。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class DiaryCreate(BaseModel):
    date: str = Field(min_length=1)
    content: str = Field(min_length=1)
    tags: List[str] = Field(default_factory=list)


class DiaryUpdate(BaseModel):
    date: Optional[str] = None
    content: Optional[str] = Field(default=None, min_length=1)
    tags: Optional[List[str]] = None
    version: Optional[int] = Field(default=None, ge=1)


class DiaryResponse(BaseModel):
    id: str
    date: str
    content: str
    content_hash: str
    version: int
    tags: List[str]
    created_at: str
    updated_at: str
    deleted_at: Optional[str]
    view_count: int = 0
    last_viewed_at: Optional[str] = None


class ViewRecordResponse(BaseModel):
    diary_id: str
    view_count: int
    viewed_at: str


class StatisticsResponse(BaseModel):
    total_diaries: int
    total_views: int
    average_views: float
    most_viewed_id: Optional[str]
    most_viewed_count: int
    least_viewed_id: Optional[str]
    least_viewed_count: int


class DiaryListResponse(BaseModel):
    items: List[DiaryResponse]
    next_cursor: Optional[str] = None


class TagCreate(BaseModel):
    name: str = Field(min_length=1)


class TagUpdate(BaseModel):
    name: str = Field(min_length=1)


class TagResponse(BaseModel):
    id: str
    name: str
    created_at: str


class TagListResponse(BaseModel):
    items: List[TagResponse]
    next_cursor: Optional[str] = None


class VoiceProfileResponse(BaseModel):
    id: str
    name: str
    provider: str
    language: str
    voice_name: str
    speed: float
    pitch: float
    offline_supported: bool
    config_hash: str
    created_at: str


class VoiceListResponse(BaseModel):
    items: List[VoiceProfileResponse]


class AudioGenerateRequest(BaseModel):
    voice_id: Optional[str] = None


class AudioAssetResponse(BaseModel):
    id: str
    diary_id: str
    voice_id: str
    content_hash: str
    voice_config_hash: str
    duration_ms: int
    format: str
    file_hash: str
    status: str
    created_at: str
    download_url: str


class AudioAssetListResponse(BaseModel):
    items: List[AudioAssetResponse]


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict


class HealthResponse(BaseModel):
    status: str
    service: str


class SyncOperation(BaseModel):
    entity_type: str = "diary"
    entity_id: str
    action: str
    base_version: Optional[int] = Field(default=None, ge=1)
    data: dict = Field(default_factory=dict)


class SyncPushRequest(BaseModel):
    operations: List[SyncOperation] = Field(default_factory=list, max_length=100)


class SyncPullResponse(BaseModel):
    items: List[dict]
    next_cursor: int


class SyncPushResponse(BaseModel):
    items: List[dict]


class PlaybackRecordRequest(BaseModel):
    id: Optional[str] = None
    device_id: str = Field(min_length=1)
    diary_id: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    round_number: int = Field(ge=1, le=2)
    position_ms: int = Field(ge=0)
    status: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)


class PlaybackRecordResponse(BaseModel):
    id: str
    device_id: str
    diary_id: str
    voice_id: str
    round_number: int
    position_ms: int
    status: str
    updated_at: str
