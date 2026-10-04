from datetime import date
from fastapi import APIRouter, Depends, Query, Request

from server.schemas import DailyViewStatisticsResponse, DiaryListResponse
from server.logging_config import get_logger
from server.service import DiaryService, ServiceError

router = APIRouter()
logger = get_logger("diary.statistics")


def get_service(request: Request) -> DiaryService:
    return request.app.state.diary_service


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ServiceError('INVALID_DATE_RANGE', f'{field}日期格式无效', 422) from error


@router.get('/statistics/daily', response_model=DailyViewStatisticsResponse)
def daily_statistics(
    start_date: str = Query(min_length=10, max_length=10),
    end_date: str = Query(min_length=10, max_length=10),
    service: DiaryService = Depends(get_service),
) -> DailyViewStatisticsResponse:
    logger.info("daily_statistics_requested", extra={"start_date": start_date, "end_date": end_date})
    start = parse_date(start_date, '开始')
    end = parse_date(end_date, '结束')
    if start > end:
        raise ServiceError('INVALID_DATE_RANGE', '开始日期不能晚于结束日期', 422)
    if (end - start).days > 366:
        raise ServiceError('INVALID_DATE_RANGE', '日期范围不能超过一年', 422)
    return DailyViewStatisticsResponse(**service.daily_view_statistics(
        start.isoformat(), end.isoformat()))


@router.get('/calendar/diaries', response_model=DiaryListResponse)
def calendar_diaries(
    date_value: str = Query(alias='date', min_length=10, max_length=10),
    service: DiaryService = Depends(get_service),
) -> DiaryListResponse:
    logger.info("calendar_diaries_requested", extra={"date": date_value})
    selected = parse_date(date_value, '查询')
    return DiaryListResponse(items=service.diaries_by_date(selected.isoformat()))