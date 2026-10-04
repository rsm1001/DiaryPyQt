"""日记后端 FastAPI 入口。"""
from pathlib import Path
from typing import Iterator, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Path as ApiPath, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from server.audio_provider import EdgeTTSProvider
from server.audio_repository import AudioRepository
from server.audio_service import AudioService
from server.config.settings import Settings, get_settings
from server.logging_config import (
    configure_logging,
    current_request_id,
    get_logger,
    reset_request_id,
    set_request_id,
)
from server.repository import DiaryRepository
from server.sync.repository import SyncRepository
from server.sync.service import SyncService
from server.statistics.routes import router as statistics_router
from server.schemas import (
    AudioAssetListResponse,
    AudioAssetResponse,
    AudioGenerateRequest,
    DiaryCreate,
    DiaryListResponse,
    DiaryResponse,
    DiaryUpdate,
    ErrorResponse,
    HealthResponse,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagUpdate,
    VoiceListResponse,
    PlaybackRecordRequest,
    PlaybackRecordResponse,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    StatisticsResponse,
    ViewBaselineRequest,
    ViewRecordRequest,
    ViewRecordResponse,
)
from server.service import DiaryService, ServiceError


configure_logging()
logger = get_logger("diary.api")
router = APIRouter(prefix="/api/v1")


def get_service(request: Request) -> DiaryService:
    """从应用状态获取日记服务。"""
    return request.app.state.diary_service


def get_audio_service(request: Request) -> AudioService:
    """从应用状态获取音频服务。"""
    return request.app.state.audio_service


def get_sync_service(request: Request) -> SyncService:
    """从应用状态获取同步服务。"""
    return request.app.state.sync_service


def _audio_response(asset: dict) -> AudioAssetResponse:
    """将数据库音频资源转换为 API 响应。"""
    return AudioAssetResponse(
        id=asset["id"],
        diary_id=asset["diary_id"],
        voice_id=asset["voice_id"],
        content_hash=asset["content_hash"],
        voice_config_hash=asset["voice_config_hash"],
        duration_ms=asset["duration_ms"],
        format=asset["format"],
        file_hash=asset["file_hash"],
        status=asset["status"],
        created_at=asset["created_at"],
        download_url=f"/api/v1/audio-assets/{asset['id']}/download",
    )


@router.get("/diaries", response_model=DiaryListResponse)
def list_diaries(
    include_deleted: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: DiaryService = Depends(get_service),
) -> DiaryListResponse:
    """查询日记列表。"""
    logger.info("diary_list_requested", extra={"limit": limit, "offset": offset})
    items = service.list_diaries(include_deleted, limit, offset)
    return DiaryListResponse(items=items)


@router.get("/trash", response_model=DiaryListResponse)
def list_trash(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: DiaryService = Depends(get_service),
) -> DiaryListResponse:
    """查询回收站日记列表。"""
    logger.info("trash_list_requested", extra={"limit": limit, "offset": offset})
    return DiaryListResponse(items=service.list_deleted(limit, offset))


@router.post("/trash/{diary_id}/restore", response_model=DiaryResponse)
def restore_trash(
    diary_id: str,
    version: Optional[int] = Query(default=None, ge=1),
    service: DiaryService = Depends(get_service),
) -> DiaryResponse:
    """从回收站恢复日记。"""
    logger.info("trash_restore_requested", extra={"diary_id": diary_id})
    return DiaryResponse(**service.restore_diary(diary_id, version))


@router.delete("/trash/{diary_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_trash(
    diary_id: str,
    service: DiaryService = Depends(get_service),
) -> Response:
    """永久删除回收站中的日记。"""
    logger.info("trash_permanent_delete_requested", extra={"diary_id": diary_id})
    service.permanently_delete_diary(diary_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/trash/{diary_id}/versions/{version}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_trash_versioned(
    diary_id: str,
    version: int = ApiPath(ge=1),
    service: DiaryService = Depends(get_service),
) -> Response:
    """仅在回收站日记版本未变化时永久删除。"""
    logger.info("trash_versioned_delete_requested", extra={"diary_id": diary_id})
    service.permanently_delete_diary(diary_id, version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/diaries/{diary_id}", response_model=DiaryResponse)
def get_diary(diary_id: str, service: DiaryService = Depends(get_service)) -> DiaryResponse:
    """查询单条日记。"""
    logger.info("diary_requested", extra={"diary_id": diary_id})
    return service.get_diary(diary_id)


@router.post("/diaries", response_model=DiaryResponse, status_code=status.HTTP_201_CREATED)
def create_diary(payload: DiaryCreate, service: DiaryService = Depends(get_service)) -> DiaryResponse:
    """创建日记。"""
    logger.info("diary_create_requested")
    return service.create_diary(payload)


@router.patch("/diaries/{diary_id}", response_model=DiaryResponse)
def update_diary(
    diary_id: str,
    payload: DiaryUpdate,
    service: DiaryService = Depends(get_service),
) -> DiaryResponse:
    """更新日记并递增版本。"""
    logger.info("diary_update_requested", extra={"diary_id": diary_id})
    return service.update_diary(diary_id, payload)


@router.delete("/diaries/{diary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diary(
    diary_id: str,
    version: Optional[int] = Query(default=None, ge=1),
    service: DiaryService = Depends(get_service),
) -> Response:
    """软删除日记。"""
    logger.info("diary_delete_requested", extra={"diary_id": diary_id})
    service.delete_diary(diary_id, version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/diaries/{diary_id}/view-baselines", response_model=DiaryResponse)
def import_diary_view_baseline(
    diary_id: str, payload: ViewBaselineRequest,
    service: DiaryService = Depends(get_service),
) -> DiaryResponse:
    """幂等补入初始电脑统计，保留服务器现有的新查看事件。"""
    logger.info("diary_view_baseline_requested", extra={"diary_id": diary_id})
    service.import_view_baseline(diary_id, payload.source_id,
                                 payload.view_count, payload.last_viewed_at)
    return DiaryResponse(**service.get_diary(diary_id))


@router.post("/diaries/{diary_id}/view", response_model=ViewRecordResponse)
def record_diary_view(
    diary_id: str,
    payload: Optional[ViewRecordRequest] = None,
    service: DiaryService = Depends(get_service),
) -> ViewRecordResponse:
    """按事件 ID 去重，同时兼容没有请求体的旧客户端。"""
    logger.info("diary_view_recorded", extra={"diary_id": diary_id})
    return ViewRecordResponse(**service.record_view(
        diary_id,
        event_id=payload.event_id if payload else None,
        viewed_at=payload.viewed_at if payload else None,
    ))


@router.get("/statistics", response_model=StatisticsResponse)
def get_statistics(service: DiaryService = Depends(get_service)) -> StatisticsResponse:
    """查询查看次数统计。"""
    logger.info("diary_statistics_requested")
    return StatisticsResponse(**service.view_statistics())


@router.get("/sync/pull", response_model=SyncPullResponse)
def pull_sync(
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    sync_service: SyncService = Depends(get_sync_service),
) -> SyncPullResponse:
    """拉取游标之后的增量同步变更。"""
    logger.info("sync_pull_requested", extra={"cursor": cursor, "limit": limit})
    return SyncPullResponse(**sync_service.pull(cursor, limit))


@router.post("/sync/push", response_model=SyncPushResponse)
def push_sync(
    payload: SyncPushRequest,
    sync_service: SyncService = Depends(get_sync_service),
) -> SyncPushResponse:
    """接收客户端推送的同步操作。"""
    logger.info("sync_push_requested", extra={"count": len(payload.operations)})
    result = sync_service.push([item.model_dump() for item in payload.operations])
    return SyncPushResponse(**result)


@router.post("/playback-records", response_model=PlaybackRecordResponse)
def save_playback(
    payload: PlaybackRecordRequest,
    sync_service: SyncService = Depends(get_sync_service),
) -> PlaybackRecordResponse:
    """保存播放进度记录。"""
    logger.info("playback_record_requested", extra={"diary_id": payload.diary_id})
    return PlaybackRecordResponse(**sync_service.save_playback(payload.model_dump()))


@router.get("/playback-records", response_model=List[PlaybackRecordResponse])
def list_playback_records(
    device_id: Optional[str] = Query(default=None, min_length=1),
    diary_id: Optional[str] = Query(default=None),
    voice_id: Optional[str] = Query(default=None),
    sync_service: SyncService = Depends(get_sync_service),
) -> List[PlaybackRecordResponse]:
    """查询指定设备的播放恢复记录。"""
    logger.info("playback_record_list_requested", extra={"device_id": device_id})
    return [PlaybackRecordResponse(**item) for item in sync_service.list_playback(
        device_id, diary_id, voice_id)]

@router.get("/tags", response_model=TagListResponse)
def list_tags(service: DiaryService = Depends(get_service)) -> TagListResponse:
    """查询标签列表。"""
    logger.info("tag_list_requested")
    return TagListResponse(items=service.list_tags())


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, service: DiaryService = Depends(get_service)) -> TagResponse:
    """创建标签。"""
    logger.info("tag_create_requested")
    return TagResponse(**service.create_tag(payload.name))


@router.patch("/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: str,
    payload: TagUpdate,
    service: DiaryService = Depends(get_service),
) -> TagResponse:
    """修改标签名称。"""
    logger.info("tag_update_requested", extra={"tag_id": tag_id})
    return TagResponse(**service.update_tag(tag_id, payload.name))


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: str, service: DiaryService = Depends(get_service)) -> Response:
    """删除未被使用的标签。"""
    logger.info("tag_delete_requested", extra={"tag_id": tag_id})
    service.delete_tag(tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/voices", response_model=VoiceListResponse)
def list_voices(audio_service: AudioService = Depends(get_audio_service)) -> VoiceListResponse:
    """查询语音包。"""
    logger.info("voice_list_requested")
    return VoiceListResponse(items=audio_service.list_voices())


@router.post("/diaries/{diary_id}/audio/generate", response_model=AudioAssetResponse)
async def generate_audio(
    diary_id: str,
    payload: AudioGenerateRequest,
    audio_service: AudioService = Depends(get_audio_service),
) -> AudioAssetResponse:
    """生成或复用日记音频。"""
    logger.info("audio_generation_requested", extra={"diary_id": diary_id})
    asset = await audio_service.generate(diary_id, payload.voice_id)
    return _audio_response(asset)


@router.get("/diaries/{diary_id}/audio", response_model=AudioAssetListResponse)
def list_audio(
    diary_id: str,
    audio_service: AudioService = Depends(get_audio_service),
) -> AudioAssetListResponse:
    """查询日记已生成的音频。"""
    logger.info("audio_list_requested", extra={"diary_id": diary_id})
    assets = audio_service.list_assets(diary_id)
    return AudioAssetListResponse(items=[_audio_response(asset) for asset in assets])


@router.get("/audio-assets/{asset_id}/download", response_model=None)
def download_audio(
    asset_id: str,
    request: Request,
    audio_service: AudioService = Depends(get_audio_service),
) -> Response:
    """下载音频文件，支持 Range 分段以便播放器续传和拖动。"""
    asset = audio_service.get_asset(asset_id)
    path = Path(asset["file_path"])
    file_size = path.stat().st_size
    common_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": f'"{asset["file_hash"]}"',
    }
    range_header = request.headers.get("range")
    logger.info(
        "audio_download_requested",
        extra={"asset_id": asset_id, "range": range_header or "full"},
    )
    if not range_header:
        return FileResponse(
            path,
            media_type="audio/mpeg",
            filename=f"{asset_id}.mp3",
            headers=common_headers,
        )

    start, end = _parse_byte_range(range_header, file_size)
    if start is None or end is None:
        return Response(
            status_code=416,
            headers={**common_headers, "Content-Range": f"bytes */{file_size}"},
        )
    length = end - start + 1
    headers = {
        **common_headers,
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(length),
    }
    return StreamingResponse(
        _read_file_range(path, start, length),
        status_code=206,
        media_type="audio/mpeg",
        headers=headers,
    )


def _parse_byte_range(value: str, file_size: int) -> tuple[int | None, int | None]:
    if not value.startswith("bytes=") or "," in value:
        return None, None
    raw = value[6:].strip()
    if "-" not in raw:
        return None, None
    start_text, end_text = raw.split("-", 1)
    try:
        if not start_text:
            suffix = int(end_text)
            if suffix <= 0:
                return None, None
            return max(0, file_size - suffix), file_size - 1
        start = int(start_text)
        end = file_size - 1 if not end_text else int(end_text)
    except ValueError:
        return None, None
    if start < 0 or start >= file_size or end < start:
        return None, None
    return start, min(end, file_size - 1)


def _read_file_range(path: Path, start: int, length: int) -> Iterator[bytes]:
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = length
        while remaining > 0:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                return
            remaining -= len(chunk)
            yield chunk


def create_app(
    settings: Optional[Settings] = None,
    service: Optional[DiaryService] = None,
    audio_service: Optional[AudioService] = None,
) -> FastAPI:
    """创建日记后端应用。"""
    active_settings = settings or get_settings()
    sync_repository = SyncRepository(active_settings.db_path)
    active_service = service or DiaryService(
        DiaryRepository(active_settings.db_path), sync_repository=sync_repository
    )
    active_audio_service = audio_service or AudioService(
        diary_service=active_service,
        audio_repository=AudioRepository(active_settings.db_path),
        provider=EdgeTTSProvider(),
        audio_root=active_settings.audio_root,
        default_voice_name=active_settings.default_voice_name,
        generation_timeout_seconds=active_settings.audio_generation_timeout_seconds,
    )
    app = FastAPI(title="Diary Server", version="1.0.0")
    app.state.diary_service = active_service
    app.state.audio_service = active_audio_service
    app.state.sync_service = SyncService(active_service, sync_repository)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        logger.warning(
            "diary_service_error",
            extra={"path": request.url.path, "error_code": exc.code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=exc.code,
                message=exc.message,
                request_id=current_request_id(),
                details=exc.details,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("diary_unexpected_error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="INTERNAL_SERVER_ERROR",
                message="服务器内部错误",
                request_id=current_request_id(),
                details={},
            ).model_dump(),
        )

    @app.get("/health", response_model=HealthResponse)
    def health_check() -> HealthResponse:
        """检查日记后端状态。"""
        logger.info("diary_health_check")
        return HealthResponse(status="ok", service="diary-server",
                              capabilities=["view_event_idempotent_v1", "desktop_view_baseline_v1"])

    app.include_router(router)
    app.include_router(statistics_router, prefix='/api/v1')
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("server.main:app", host=settings.host, port=settings.port)
