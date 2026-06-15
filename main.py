from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import TagStatus, ExceptionType, TicketStatus
from schemas import (
    TagCreate, TagUpdate, TagStatusUpdate, TagResponse, TagListResponse,
    IssueTagRequest, ReturnTagRequest, IssueRecordResponse, IssueRecordListResponse,
    CheckRecordCreate, CheckRecordResponse, CheckRecordListResponse,
    StatisticsResponse, OvertimeAreaStats, ResponsibleClosureStats, PendingCheckStats,
    AlertResponse, AlertItem, ErrorResponse,
    ExceptionTicketCreate, ExceptionTicketHandle,
    ExceptionTicketResponse, ExceptionTicketListResponse,
    ExceptionTicketStats
)
from crud import (
    BusinessError, create_tag, get_tag, get_tag_by_code, list_tags,
    update_tag, update_tag_status, delete_tag, issue_tag, return_tag, check_tag,
    list_issue_records, list_check_records,
    get_overtime_high_risk_areas, get_responsible_closure_rates,
    get_pending_check_stats, get_alerts, update_overtime_tags,
    create_exception_ticket, get_exception_ticket, list_exception_tickets,
    handle_exception_ticket, get_exception_ticket_stats
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="临时寄物牌管理系统",
    description="寄物牌发放、归还、过期占用处理和责任追踪 RESTful API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auto_update_overtime(request, call_next):
    db = next(get_db())
    try:
        update_overtime_tags(db)
    except Exception:
        pass
    finally:
        db.close()
    response = await call_next(request)
    return response


@app.exception_handler(BusinessError)
async def business_error_handler(request, exc: BusinessError):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.code,
        content={
            "code": exc.code,
            "message": exc.message,
            "conflict_object": exc.conflict_object,
            "current_status": exc.current_status
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "conflict_object": None,
            "current_status": None
        }
    )


@app.get("/", tags=["系统"])
async def root():
    return {
        "code": 200,
        "message": "临时寄物牌管理系统 API 服务运行中",
        "data": {
            "version": "1.0.0",
            "port": 8125,
            "statuses": [s.value for s in TagStatus]
        }
    }


@app.get("/api/tags", response_model=TagListResponse, tags=["寄物牌管理"])
async def get_tags(
    area: Optional[str] = Query(None, description="所属区域"),
    group_name: Optional[str] = Query(None, description="分组"),
    responsible_person: Optional[str] = Query(None, description="责任人"),
    status: Optional[str] = Query(None, description="状态"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    is_overtime: Optional[bool] = Query(None, description="是否超时"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    items, total = list_tags(
        db, area=area, group_name=group_name,
        responsible_person=responsible_person, status=status,
        start_date=start_date, end_date=end_date,
        is_overtime=is_overtime, skip=skip, limit=page_size
    )
    return TagListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@app.get("/api/tags/{tag_id}", response_model=TagResponse, tags=["寄物牌管理"])
async def get_tag_detail(tag_id: int, db: Session = Depends(get_db)):
    tag = get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail=f"寄物牌 ID {tag_id} 不存在")
    return tag


@app.post("/api/tags", response_model=TagResponse, tags=["寄物牌管理"])
async def create_new_tag(tag: TagCreate, db: Session = Depends(get_db)):
    return create_tag(db, tag)


@app.put("/api/tags/{tag_id}", response_model=TagResponse, tags=["寄物牌管理"])
async def update_tag_info(tag_id: int, tag_update: TagUpdate, db: Session = Depends(get_db)):
    return update_tag(db, tag_id, tag_update)


@app.put("/api/tags/{tag_id}/status", response_model=TagResponse, tags=["寄物牌管理"])
async def change_tag_status(tag_id: int, status_update: TagStatusUpdate, db: Session = Depends(get_db)):
    return update_tag_status(db, tag_id, status_update.status, status_update.note)


@app.delete("/api/tags/{tag_id}", tags=["寄物牌管理"])
async def delete_tag_by_id(tag_id: int, db: Session = Depends(get_db)):
    delete_tag(db, tag_id)
    return {"code": 200, "message": f"寄物牌 ID {tag_id} 删除成功"}


@app.post("/api/tags/issue", tags=["寄物牌业务"])
async def issue_new_tag(request: IssueTagRequest, db: Session = Depends(get_db)):
    tag, issue_record = issue_tag(db, request)
    return {
        "code": 200,
        "message": "发放成功",
        "data": {
            "tag": TagResponse.model_validate(tag),
            "issue_record": IssueRecordResponse.model_validate(issue_record)
        }
    }


@app.post("/api/tags/{tag_code}/return", tags=["寄物牌业务"])
async def return_tag_by_code(tag_code: str, request: ReturnTagRequest, db: Session = Depends(get_db)):
    tag, issue_record = return_tag(db, tag_code, request)
    return {
        "code": 200,
        "message": "归还成功",
        "data": {
            "tag": TagResponse.model_validate(tag),
            "issue_record": IssueRecordResponse.model_validate(issue_record) if issue_record else None
        }
    }


@app.post("/api/tags/{tag_code}/check", tags=["寄物牌业务"])
async def check_tag_by_code(tag_code: str, check_data: CheckRecordCreate, db: Session = Depends(get_db)):
    tag, check_record, issue_record = check_tag(db, tag_code, check_data)
    return {
        "code": 200,
        "message": "核对完成",
        "data": {
            "tag": TagResponse.model_validate(tag),
            "check_record": CheckRecordResponse.model_validate(check_record),
            "issue_record": IssueRecordResponse.model_validate(issue_record)
        }
    }


@app.get("/api/issue-records", response_model=IssueRecordListResponse, tags=["发放记录"])
async def get_issue_records(
    tag_code: Optional[str] = Query(None, description="寄物牌编号"),
    area: Optional[str] = Query(None, description="所属区域"),
    group_name: Optional[str] = Query(None, description="分组"),
    responsible_person: Optional[str] = Query(None, description="责任人"),
    user_name: Optional[str] = Query(None, description="使用人"),
    status: Optional[str] = Query(None, description="记录状态"),
    is_overtime: Optional[int] = Query(None, description="是否超时 0=否 1=是"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    items, total = list_issue_records(
        db, tag_code=tag_code, area=area, group_name=group_name,
        responsible_person=responsible_person, user_name=user_name,
        status=status, is_overtime=is_overtime,
        start_date=start_date, end_date=end_date,
        skip=skip, limit=page_size
    )
    return IssueRecordListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@app.get("/api/check-records", response_model=CheckRecordListResponse, tags=["核对记录"])
async def get_check_records(
    tag_code: Optional[str] = Query(None, description="寄物牌编号"),
    area: Optional[str] = Query(None, description="所属区域"),
    group_name: Optional[str] = Query(None, description="分组"),
    responsible_person: Optional[str] = Query(None, description="责任人"),
    is_closed: Optional[int] = Query(None, description="是否闭环 0=未闭环 1=已闭环"),
    check_person: Optional[str] = Query(None, description="核对人"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    items, total = list_check_records(
        db, tag_code=tag_code, area=area, group_name=group_name,
        responsible_person=responsible_person, is_closed=is_closed,
        check_person=check_person,
        start_date=start_date, end_date=end_date,
        skip=skip, limit=page_size
    )
    return CheckRecordListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@app.get("/api/statistics", response_model=StatisticsResponse, tags=["统计分析"])
async def get_statistics(db: Session = Depends(get_db)):
    overtime_areas = get_overtime_high_risk_areas(db)
    closure_rates = get_responsible_closure_rates(db)
    pending_stats = get_pending_check_stats(db)
    ticket_stats = get_exception_ticket_stats(db)

    return StatisticsResponse(
        overtime_high_risk_areas=[
            OvertimeAreaStats(**area) for area in overtime_areas
        ],
        responsible_closure_rates=[
            ResponsibleClosureStats(**rate) for rate in closure_rates
        ],
        pending_check_stats=PendingCheckStats(
            pending_count=pending_stats["pending_count"],
            pending_tags=[TagResponse.model_validate(t) for t in pending_stats["pending_tags"]]
        ),
        exception_ticket_stats=ExceptionTicketStats(
            pending_count=ticket_stats["pending_count"],
            closed_count=ticket_stats["closed_count"],
            by_responsible=ticket_stats["by_responsible"],
            by_area=ticket_stats["by_area"]
        )
    )


@app.get("/api/alerts", response_model=AlertResponse, tags=["自动预警"])
async def get_all_alerts(db: Session = Depends(get_db)):
    alerts = get_alerts(db)
    return AlertResponse(
        alerts=[AlertItem(**alert) for alert in alerts],
        total=len(alerts)
    )


@app.post("/api/exception-tickets", response_model=ExceptionTicketResponse, tags=["异常工单"])
async def create_new_exception_ticket(
    ticket_data: ExceptionTicketCreate,
    db: Session = Depends(get_db)
):
    return create_exception_ticket(db, ticket_data)


@app.get("/api/exception-tickets", response_model=ExceptionTicketListResponse, tags=["异常工单"])
async def get_exception_tickets(
    tag_code: Optional[str] = Query(None, description="寄物牌编号"),
    area: Optional[str] = Query(None, description="所属区域"),
    group_name: Optional[str] = Query(None, description="分组"),
    responsible_person: Optional[str] = Query(None, description="责任人"),
    exception_type: Optional[str] = Query(None, description="异常类型"),
    ticket_status: Optional[str] = Query(None, description="处理状态"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    items, total = list_exception_tickets(
        db, tag_code=tag_code, area=area, group_name=group_name,
        responsible_person=responsible_person, exception_type=exception_type,
        ticket_status=ticket_status, start_date=start_date, end_date=end_date,
        skip=skip, limit=page_size
    )
    return ExceptionTicketListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@app.get("/api/exception-tickets/{ticket_id}", response_model=ExceptionTicketResponse, tags=["异常工单"])
async def get_exception_ticket_detail(ticket_id: int, db: Session = Depends(get_db)):
    ticket = get_exception_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"异常工单 ID {ticket_id} 不存在")
    return ticket


@app.put("/api/exception-tickets/{ticket_id}/handle", response_model=ExceptionTicketResponse, tags=["异常工单"])
async def handle_exception_ticket_by_id(
    ticket_id: int,
    handle_data: ExceptionTicketHandle,
    db: Session = Depends(get_db)
):
    return handle_exception_ticket(db, ticket_id, handle_data)


@app.get("/api/status-options", tags=["系统"])
async def get_status_options():
    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "tag_statuses": [
                {"value": s.value, "key": s.name} for s in TagStatus
            ],
            "exception_types": [
                {"value": s.value, "key": s.name} for s in ExceptionType
            ],
            "ticket_statuses": [
                {"value": s.value, "key": s.name} for s in TicketStatus
            ]
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8125)
