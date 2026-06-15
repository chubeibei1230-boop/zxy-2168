from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case
from typing import List, Optional, Tuple

from models import LuggageTag, TagIssueRecord, TagCheckRecord, TagStatus, TagExceptionTicket, ExceptionType, TicketStatus
from schemas import (
    TagCreate, TagUpdate, IssueTagRequest, ReturnTagRequest,
    CheckRecordCreate, ExceptionTicketCreate, ExceptionTicketHandle
)


class BusinessError(Exception):
    def __init__(self, message: str, conflict_object: str = None, current_status: str = None, code: int = 400):
        self.message = message
        self.conflict_object = conflict_object
        self.current_status = current_status
        self.code = code
        super().__init__(message)


def _check_issue_allowed(db: Session, tag: LuggageTag):
    if tag.status == TagStatus.IN_USE:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 正在使用中，无法再次发放",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=409
        )
    if tag.status == TagStatus.OVERTIME:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 处于超时占用状态，无法再次发放",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=409
        )
    if tag.status == TagStatus.DISABLED:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 已停用，无法发放",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=409
        )
    if tag.status == TagStatus.PENDING_CHECK:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 处于待核对状态，无法发放",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=409
        )
    unclosed_ticket = db.query(TagExceptionTicket).filter(
        and_(
            TagExceptionTicket.tag_id == tag.id,
            TagExceptionTicket.ticket_status != TicketStatus.CLOSED
        )
    ).first()
    if unclosed_ticket:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 存在未闭环异常工单（工单号#{unclosed_ticket.id}），无法发放",
            conflict_object=f"异常工单#{unclosed_ticket.id}",
            current_status=unclosed_ticket.ticket_status.value,
            code=409
        )


def _check_return_allowed(tag: LuggageTag):
    if tag.status not in [TagStatus.IN_USE, TagStatus.OVERTIME]:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 当前状态为 {tag.status.value}，无法归还",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=409
        )


def _check_manual_restore_allowed(tag: LuggageTag):
    if tag.status == TagStatus.OVERTIME:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 处于超时占用状态，需先核对后才能恢复可用",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=409
        )
    if tag.status == TagStatus.PENDING_CHECK:
        raise BusinessError(
            f"寄物牌 {tag.tag_code} 处于待核对状态，需先核对后才能恢复可用",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=409
        )


def create_tag(db: Session, tag: TagCreate) -> LuggageTag:
    existing = db.query(LuggageTag).filter(LuggageTag.tag_code == tag.tag_code).first()
    if existing:
        raise BusinessError(
            f"寄物牌编号 {tag.tag_code} 已存在",
            conflict_object=tag.tag_code,
            current_status=existing.status.value,
            code=409
        )

    db_tag = LuggageTag(
        tag_code=tag.tag_code,
        area=tag.area,
        group_name=tag.group_name,
        retention_hours=tag.retention_hours,
        responsible_person=tag.responsible_person,
        status=TagStatus.PENDING_ISSUE
    )
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag


def get_tag(db: Session, tag_id: int) -> Optional[LuggageTag]:
    return db.query(LuggageTag).filter(LuggageTag.id == tag_id).first()


def get_tag_by_code(db: Session, tag_code: str) -> Optional[LuggageTag]:
    return db.query(LuggageTag).filter(LuggageTag.tag_code == tag_code).first()


def list_tags(
    db: Session,
    area: Optional[str] = None,
    group_name: Optional[str] = None,
    responsible_person: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_overtime: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[LuggageTag], int]:
    query = db.query(LuggageTag)

    if area:
        query = query.filter(LuggageTag.area == area)
    if group_name:
        query = query.filter(LuggageTag.group_name == group_name)
    if responsible_person:
        query = query.filter(LuggageTag.responsible_person == responsible_person)
    if status:
        status_enum = TagStatus(status) if status in [s.value for s in TagStatus] else None
        if status_enum:
            query = query.filter(LuggageTag.status == status_enum)
    if start_date:
        query = query.filter(LuggageTag.issue_time >= start_date)
    if end_date:
        query = query.filter(LuggageTag.issue_time <= end_date)
    if is_overtime is not None:
        if is_overtime:
            query = query.filter(LuggageTag.status == TagStatus.OVERTIME)
        else:
            query = query.filter(LuggageTag.status != TagStatus.OVERTIME)

    total = query.count()
    items = query.order_by(LuggageTag.id.desc()).offset(skip).limit(limit).all()
    return items, total


def update_tag(db: Session, tag_id: int, tag_update: TagUpdate) -> Optional[LuggageTag]:
    db_tag = get_tag(db, tag_id)
    if not db_tag:
        raise BusinessError(f"寄物牌 ID {tag_id} 不存在", code=404)

    update_data = tag_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tag, key, value)

    db_tag.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_tag)
    return db_tag


def update_tag_status(db: Session, tag_id: int, new_status: str, note: str = None) -> Optional[LuggageTag]:
    db_tag = get_tag(db, tag_id)
    if not db_tag:
        raise BusinessError(f"寄物牌 ID {tag_id} 不存在", code=404)

    try:
        target_status = TagStatus(new_status)
    except ValueError:
        raise BusinessError(
            f"无效的状态值: {new_status}",
            conflict_object=new_status,
            current_status=db_tag.status.value,
            code=400
        )

    if target_status == db_tag.status:
        return db_tag

    if target_status == TagStatus.AVAILABLE:
        _check_manual_restore_allowed(db_tag)

    if target_status == TagStatus.DISABLED:
        if db_tag.status == TagStatus.IN_USE:
            raise BusinessError(
                f"寄物牌 {db_tag.tag_code} 正在使用中，无法停用",
                conflict_object=db_tag.tag_code,
                current_status=db_tag.status.value,
                code=409
            )

    if target_status == TagStatus.PENDING_ISSUE:
        if db_tag.status not in [TagStatus.AVAILABLE, TagStatus.DISABLED]:
            raise BusinessError(
                f"寄物牌 {db_tag.tag_code} 当前状态为 {db_tag.status.value}，无法设置为待发放",
                conflict_object=db_tag.tag_code,
                current_status=db_tag.status.value,
                code=409
            )

    if target_status == TagStatus.IN_USE:
        raise BusinessError(
            f"不能直接将寄物牌 {db_tag.tag_code} 设置为使用中，请通过发放接口操作",
            conflict_object=db_tag.tag_code,
            current_status=db_tag.status.value,
            code=409
        )

    if target_status == TagStatus.OVERTIME:
        raise BusinessError(
            f"不能直接将寄物牌 {db_tag.tag_code} 设置为超时占用",
            conflict_object=db_tag.tag_code,
            current_status=db_tag.status.value,
            code=409
        )

    if target_status == TagStatus.PENDING_CHECK:
        raise BusinessError(
            f"不能直接将寄物牌 {db_tag.tag_code} 设置为待核对，请通过归还接口操作",
            conflict_object=db_tag.tag_code,
            current_status=db_tag.status.value,
            code=409
        )

    db_tag.status = target_status
    if target_status == TagStatus.PENDING_ISSUE or target_status == TagStatus.AVAILABLE:
        db_tag.current_user = None
        db_tag.issue_time = None
        db_tag.expected_return_time = None
    db_tag.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_tag)
    return db_tag


def delete_tag(db: Session, tag_id: int) -> bool:
    db_tag = get_tag(db, tag_id)
    if not db_tag:
        raise BusinessError(f"寄物牌 ID {tag_id} 不存在", code=404)

    db.delete(db_tag)
    db.commit()
    return True


def issue_tag(db: Session, request: IssueTagRequest) -> Tuple[LuggageTag, TagIssueRecord]:
    update_overtime_tags(db)

    if request.tag_code:
        tag = get_tag_by_code(db, request.tag_code)
        if not tag:
            raise BusinessError(f"寄物牌 {request.tag_code} 不存在", code=404)
        _check_issue_allowed(db, tag)
    else:
        subquery = db.query(TagExceptionTicket.tag_id).filter(
            TagExceptionTicket.ticket_status != TicketStatus.CLOSED
        ).distinct()
        query = db.query(LuggageTag).filter(
            and_(
                LuggageTag.status.in_([TagStatus.PENDING_ISSUE, TagStatus.AVAILABLE]),
                LuggageTag.id.notin_(subquery)
            )
        )
        if request.area:
            query = query.filter(LuggageTag.area == request.area)
        if request.group_name:
            query = query.filter(LuggageTag.group_name == request.group_name)
        if request.responsible_person:
            query = query.filter(LuggageTag.responsible_person == request.responsible_person)

        tag = query.order_by(LuggageTag.id).first()
        if not tag:
            filters = []
            if request.area:
                filters.append(f"区域={request.area}")
            if request.group_name:
                filters.append(f"分组={request.group_name}")
            if request.responsible_person:
                filters.append(f"责任人={request.responsible_person}")
            filter_str = "、".join(filters) if filters else "所有区域"
            raise BusinessError(
                f"{filter_str} 暂无可用寄物牌",
                conflict_object=filter_str,
                current_status="无可用",
                code=404
            )

    issue_time = datetime.utcnow()
    expected_return_time = issue_time + timedelta(hours=tag.retention_hours)

    tag.status = TagStatus.IN_USE
    tag.current_user = request.user_name
    tag.issue_time = issue_time
    tag.expected_return_time = expected_return_time
    tag.updated_at = issue_time

    issue_record = TagIssueRecord(
        tag_id=tag.id,
        tag_code=tag.tag_code,
        area=tag.area,
        group_name=tag.group_name,
        responsible_person=tag.responsible_person,
        user_name=request.user_name,
        user_contact=request.user_contact,
        issue_time=issue_time,
        expected_return_time=expected_return_time,
        status="使用中"
    )
    db.add(issue_record)
    db.commit()
    db.refresh(tag)
    db.refresh(issue_record)

    return tag, issue_record


def return_tag(db: Session, tag_code: str, request: ReturnTagRequest) -> Tuple[LuggageTag, TagIssueRecord]:
    update_overtime_tags(db)

    tag = get_tag_by_code(db, tag_code)
    if not tag:
        raise BusinessError(f"寄物牌 {tag_code} 不存在", code=404)

    _check_return_allowed(tag)

    return_time = datetime.utcnow()
    is_overtime = 0
    overtime_hours = 0

    if tag.expected_return_time and return_time > tag.expected_return_time:
        is_overtime = 1
        overtime_delta = return_time - tag.expected_return_time
        overtime_hours = int(overtime_delta.total_seconds() / 3600) + 1

    latest_record = db.query(TagIssueRecord).filter(
        and_(
            TagIssueRecord.tag_id == tag.id,
            TagIssueRecord.status == "使用中"
        )
    ).order_by(TagIssueRecord.id.desc()).first()

    if latest_record:
        latest_record.actual_return_time = return_time
        latest_record.is_overtime = is_overtime
        latest_record.overtime_hours = overtime_hours
        latest_record.return_note = request.return_note
        latest_record.status = "已归还"

    if is_overtime:
        tag.status = TagStatus.PENDING_CHECK
        _auto_create_exception_ticket(
            db, tag, latest_record,
            ExceptionType.OVERTIME,
            f"寄物牌超时{overtime_hours}小时归还"
        )
    else:
        tag.status = TagStatus.AVAILABLE

    tag.current_user = None
    tag.issue_time = None
    tag.expected_return_time = None
    tag.updated_at = return_time

    db.commit()
    db.refresh(tag)
    if latest_record:
        db.refresh(latest_record)

    return tag, latest_record


def check_tag(db: Session, tag_code: str, check_data: CheckRecordCreate) -> Tuple[LuggageTag, TagCheckRecord, TagIssueRecord]:
    update_overtime_tags(db)

    tag = get_tag_by_code(db, tag_code)
    if not tag:
        raise BusinessError(f"寄物牌 {tag_code} 不存在", code=404)

    if tag.status != TagStatus.PENDING_CHECK:
        raise BusinessError(
            f"寄物牌 {tag_code} 当前状态为 {tag.status.value}，无需核对",
            conflict_object=tag_code,
            current_status=tag.status.value,
            code=409
        )

    latest_record = db.query(TagIssueRecord).filter(
        and_(
            TagIssueRecord.tag_id == tag.id,
            TagIssueRecord.status == "已归还",
            TagIssueRecord.is_overtime == 1
        )
    ).order_by(TagIssueRecord.id.desc()).first()

    if not latest_record:
        raise BusinessError(f"寄物牌 {tag_code} 没有待核对的发放记录", code=404)

    existing_check = db.query(TagCheckRecord).filter(
        TagCheckRecord.issue_record_id == latest_record.id
    ).first()
    if existing_check:
        raise BusinessError(
            f"发放记录 ID {latest_record.id} 已完成核对，不能重复核对",
            conflict_object=f"发放记录#{latest_record.id}",
            current_status="已核对",
            code=409
        )

    check_record = TagCheckRecord(
        tag_id=tag.id,
        issue_record_id=latest_record.id,
        tag_code=tag.tag_code,
        overtime_description=check_data.overtime_description,
        handling_conclusion=check_data.handling_conclusion,
        check_person=check_data.check_person,
        check_time=datetime.utcnow(),
        is_closed=check_data.is_closed
    )
    db.add(check_record)

    if check_data.is_closed:
        tag.status = TagStatus.AVAILABLE
        _close_related_tickets(
            db, tag, latest_record,
            check_data.handling_conclusion, check_data.check_person
        )
    else:
        tag.status = TagStatus.PENDING_CHECK
        existing_ticket = db.query(TagExceptionTicket).filter(
            and_(
                TagExceptionTicket.issue_record_id == latest_record.id,
                TagExceptionTicket.ticket_status != TicketStatus.CLOSED
            )
        ).first()
        if not existing_ticket:
            _auto_create_exception_ticket(
                db, tag, latest_record,
                ExceptionType.PENDING_CHECK,
                f"核对未闭环：{check_data.overtime_description}"
            )

    tag.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(tag)
    db.refresh(check_record)

    return tag, check_record, latest_record


def list_issue_records(
    db: Session,
    tag_code: Optional[str] = None,
    area: Optional[str] = None,
    group_name: Optional[str] = None,
    responsible_person: Optional[str] = None,
    user_name: Optional[str] = None,
    status: Optional[str] = None,
    is_overtime: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[TagIssueRecord], int]:
    query = db.query(TagIssueRecord)

    if tag_code:
        query = query.filter(TagIssueRecord.tag_code == tag_code)
    if area:
        query = query.filter(TagIssueRecord.area == area)
    if group_name:
        query = query.filter(TagIssueRecord.group_name == group_name)
    if responsible_person:
        query = query.filter(TagIssueRecord.responsible_person == responsible_person)
    if user_name:
        query = query.filter(TagIssueRecord.user_name.like(f"%{user_name}%"))
    if status:
        query = query.filter(TagIssueRecord.status == status)
    if is_overtime is not None:
        query = query.filter(TagIssueRecord.is_overtime == is_overtime)
    if start_date:
        query = query.filter(TagIssueRecord.issue_time >= start_date)
    if end_date:
        query = query.filter(TagIssueRecord.issue_time <= end_date)

    total = query.count()
    items = query.order_by(TagIssueRecord.id.desc()).offset(skip).limit(limit).all()
    return items, total


def list_check_records(
    db: Session,
    tag_code: Optional[str] = None,
    area: Optional[str] = None,
    group_name: Optional[str] = None,
    responsible_person: Optional[str] = None,
    is_closed: Optional[int] = None,
    check_person: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[TagCheckRecord], int]:
    query = db.query(TagCheckRecord)

    if tag_code:
        query = query.filter(TagCheckRecord.tag_code == tag_code)
    if is_closed is not None:
        query = query.filter(TagCheckRecord.is_closed == is_closed)
    if check_person:
        query = query.filter(TagCheckRecord.check_person.like(f"%{check_person}%"))
    if start_date:
        query = query.filter(TagCheckRecord.check_time >= start_date)
    if end_date:
        query = query.filter(TagCheckRecord.check_time <= end_date)

    if area or group_name or responsible_person:
        query = query.join(LuggageTag, TagCheckRecord.tag_id == LuggageTag.id)
        if area:
            query = query.filter(LuggageTag.area == area)
        if group_name:
            query = query.filter(LuggageTag.group_name == group_name)
        if responsible_person:
            query = query.filter(LuggageTag.responsible_person == responsible_person)

    total = query.count()
    items = query.order_by(TagCheckRecord.id.desc()).offset(skip).limit(limit).all()
    return items, total


def get_overtime_high_risk_areas(db: Session, top_n: int = 10) -> List[dict]:
    records = db.query(
        TagIssueRecord.area,
        func.count(TagIssueRecord.id).label("total_count"),
        func.sum(TagIssueRecord.is_overtime).label("overtime_count")
    ).group_by(TagIssueRecord.area).all()

    result = []
    for area, total_count, overtime_count in records:
        overtime_count = overtime_count or 0
        overtime_rate = round(overtime_count / total_count * 100, 2) if total_count > 0 else 0.0
        result.append({
            "area": area,
            "total_count": total_count,
            "overtime_count": overtime_count,
            "overtime_rate": overtime_rate
        })

    result.sort(key=lambda x: x["overtime_rate"], reverse=True)
    return result[:top_n]


def get_responsible_closure_rates(db: Session) -> List[dict]:
    records = db.query(
        LuggageTag.responsible_person,
        func.count(TagCheckRecord.id).label("total_checks"),
        func.sum(TagCheckRecord.is_closed).label("closed_count")
    ).join(TagCheckRecord, LuggageTag.id == TagCheckRecord.tag_id
    ).group_by(LuggageTag.responsible_person).all()

    result = []
    for person, total_checks, closed_count in records:
        closed_count = closed_count or 0
        closure_rate = round(closed_count / total_checks * 100, 2) if total_checks > 0 else 0.0
        result.append({
            "responsible_person": person,
            "total_checks": total_checks,
            "closed_count": closed_count,
            "closure_rate": closure_rate
        })

    result.sort(key=lambda x: x["closure_rate"])
    return result


def get_pending_check_stats(db: Session) -> dict:
    update_overtime_tags(db)

    pending_tags = db.query(LuggageTag).filter(
        LuggageTag.status == TagStatus.PENDING_CHECK
    ).all()

    return {
        "pending_count": len(pending_tags),
        "pending_tags": pending_tags
    }


def get_alerts(db: Session) -> List[dict]:
    update_overtime_tags(db)
    alerts = []
    now = datetime.utcnow()

    all_tags = db.query(LuggageTag).all()
    for tag in all_tags:
        records = db.query(TagIssueRecord).filter(
            TagIssueRecord.tag_id == tag.id
        ).order_by(TagIssueRecord.id.desc()).all()

        consecutive_count = 0
        for rec in records:
            if rec.is_overtime == 1:
                consecutive_count += 1
            else:
                break

        if consecutive_count >= 3:
            alerts.append({
                "alert_type": "连续超时占用",
                "alert_level": "高",
                "target": tag.tag_code,
                "message": f"寄物牌 {tag.tag_code} 已连续 {consecutive_count} 次超时占用",
                "details": {
                    "tag_code": tag.tag_code,
                    "responsible_person": tag.responsible_person,
                    "overtime_count": consecutive_count
                }
            })

    group_stats = db.query(
        LuggageTag.group_name,
        LuggageTag.area,
        func.count(LuggageTag.id).label("total_tags"),
        func.sum(case(
            (or_(
                LuggageTag.status == TagStatus.IN_USE,
                LuggageTag.status == TagStatus.OVERTIME
            ), 1),
            else_=0
        )).label("in_use_count")
    ).group_by(LuggageTag.group_name, LuggageTag.area).all()

    for group_name, area, total_tags, in_use_count in group_stats:
        if total_tags > 0 and in_use_count / total_tags > 0.8:
            alerts.append({
                "alert_type": "分组回收偏慢",
                "alert_level": "中",
                "target": f"{area}-{group_name}",
                "message": f"区域 {area} 分组 {group_name} 寄物牌使用率达 {round(in_use_count/total_tags*100, 1)}%，回收偏慢",
                "details": {
                    "area": area,
                    "group_name": group_name,
                    "total_tags": total_tags,
                    "in_use_count": in_use_count,
                    "usage_rate": round(in_use_count / total_tags * 100, 2)
                }
            })

    unclosed_checks = db.query(
        LuggageTag.responsible_person,
        func.count(TagCheckRecord.id).label("unclosed_count")
    ).join(
        TagCheckRecord, LuggageTag.id == TagCheckRecord.tag_id
    ).filter(
        TagCheckRecord.is_closed == 0
    ).group_by(
        LuggageTag.responsible_person
    ).all()

    for person, unclosed_count in unclosed_checks:
        if unclosed_count >= 2:
            alerts.append({
                "alert_type": "异常闭环不完整",
                "alert_level": "高",
                "target": person,
                "message": f"责任人 {person} 名下有 {unclosed_count} 条未闭环记录",
                "details": {
                    "responsible_person": person,
                    "unclosed_count": unclosed_count
                }
            })

    disabled_tags = db.query(LuggageTag).filter(
        LuggageTag.status == TagStatus.DISABLED
    ).all()

    for tag in disabled_tags:
        all_records = db.query(TagIssueRecord).filter(
            TagIssueRecord.tag_id == tag.id
        ).order_by(TagIssueRecord.id.desc()).all()

        if not all_records:
            continue

        last_return_time = None
        for rec in all_records:
            if rec.actual_return_time:
                last_return_time = rec.actual_return_time
                break

        for record in all_records:
            in_7days = record.issue_time > now - timedelta(days=7)
            if not in_7days:
                continue

            issued_after_last_return = (
                last_return_time is None
                or record.issue_time > last_return_time
            )

            is_active_issue = record.actual_return_time is None

            if issued_after_last_return or is_active_issue:
                alerts.append({
                    "alert_type": "停用后误发放",
                    "alert_level": "高",
                    "target": record.tag_code,
                    "message": f"寄物牌 {record.tag_code} 已停用但近期仍有发放记录",
                    "details": {
                        "tag_code": record.tag_code,
                        "issue_time": record.issue_time.isoformat() if record.issue_time else None,
                        "user_name": record.user_name
                    }
                })
                break

    return alerts


def _auto_create_exception_ticket(
    db: Session,
    tag: LuggageTag,
    issue_record: Optional[TagIssueRecord],
    exception_type: ExceptionType,
    description: str
) -> TagExceptionTicket:
    existing = db.query(TagExceptionTicket).filter(
        and_(
            TagExceptionTicket.tag_id == tag.id,
            TagExceptionTicket.ticket_status != TicketStatus.CLOSED
        )
    ).first()
    if existing:
        return existing

    ticket = TagExceptionTicket(
        tag_id=tag.id,
        issue_record_id=issue_record.id if issue_record else None,
        tag_code=tag.tag_code,
        area=tag.area,
        group_name=tag.group_name,
        responsible_person=tag.responsible_person,
        user_name=issue_record.user_name if issue_record else tag.current_user,
        exception_type=exception_type,
        exception_description=description,
        ticket_status=TicketStatus.PENDING
    )
    db.add(ticket)
    return ticket


def _close_related_tickets(
    db: Session,
    tag: LuggageTag,
    issue_record: TagIssueRecord,
    conclusion: str,
    handler: str
):
    now = datetime.utcnow()
    tickets = db.query(TagExceptionTicket).filter(
        and_(
            TagExceptionTicket.tag_id == tag.id,
            TagExceptionTicket.ticket_status != TicketStatus.CLOSED,
            or_(
                TagExceptionTicket.issue_record_id == issue_record.id,
                TagExceptionTicket.issue_record_id.is_(None)
            )
        )
    ).all()
    for ticket in tickets:
        ticket.ticket_status = TicketStatus.CLOSED
        ticket.handling_conclusion = conclusion
        ticket.handler = handler
        ticket.handling_time = now
        ticket.updated_at = now


def create_exception_ticket(
    db: Session,
    ticket_data: ExceptionTicketCreate
) -> TagExceptionTicket:
    tag = get_tag_by_code(db, ticket_data.tag_code)
    if not tag:
        raise BusinessError(f"寄物牌 {ticket_data.tag_code} 不存在", code=404)

    try:
        ex_type = ExceptionType(ticket_data.exception_type)
    except ValueError:
        raise BusinessError(
            f"无效的异常类型: {ticket_data.exception_type}",
            conflict_object=ticket_data.exception_type,
            code=400
        )

    has_any_record = db.query(TagIssueRecord).filter(
        TagIssueRecord.tag_id == tag.id
    ).first()
    if not has_any_record:
        raise BusinessError(
            f"寄物牌 {ticket_data.tag_code} 从未发放过，无法创建异常工单",
            conflict_object=tag.tag_code,
            current_status=tag.status.value,
            code=400
        )

    existing_unclosed = db.query(TagExceptionTicket).filter(
        and_(
            TagExceptionTicket.tag_id == tag.id,
            TagExceptionTicket.ticket_status != TicketStatus.CLOSED
        )
    ).first()
    if existing_unclosed:
        raise BusinessError(
            f"寄物牌 {ticket_data.tag_code} 已存在未闭环异常工单（工单号#{existing_unclosed.id}），不能重复创建",
            conflict_object=f"异常工单#{existing_unclosed.id}",
            current_status=existing_unclosed.ticket_status.value,
            code=409
        )

    active_record = None
    if tag.status in [TagStatus.IN_USE, TagStatus.OVERTIME]:
        active_record = db.query(TagIssueRecord).filter(
            and_(
                TagIssueRecord.tag_id == tag.id,
                TagIssueRecord.status == "使用中"
            )
        ).order_by(TagIssueRecord.id.desc()).first()
    elif tag.status == TagStatus.PENDING_CHECK:
        active_record = db.query(TagIssueRecord).filter(
            and_(
                TagIssueRecord.tag_id == tag.id,
                TagIssueRecord.status == "已归还",
                TagIssueRecord.is_overtime == 1
            )
        ).order_by(TagIssueRecord.id.desc()).first()

    ticket = TagExceptionTicket(
        tag_id=tag.id,
        issue_record_id=active_record.id if active_record else None,
        tag_code=tag.tag_code,
        area=tag.area,
        group_name=tag.group_name,
        responsible_person=tag.responsible_person,
        user_name=active_record.user_name if active_record else None,
        exception_type=ex_type,
        exception_description=ticket_data.exception_description,
        ticket_status=TicketStatus.PENDING
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_exception_ticket(db: Session, ticket_id: int) -> Optional[TagExceptionTicket]:
    return db.query(TagExceptionTicket).filter(TagExceptionTicket.id == ticket_id).first()


def list_exception_tickets(
    db: Session,
    tag_code: Optional[str] = None,
    area: Optional[str] = None,
    group_name: Optional[str] = None,
    responsible_person: Optional[str] = None,
    exception_type: Optional[str] = None,
    ticket_status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[TagExceptionTicket], int]:
    query = db.query(TagExceptionTicket)

    if tag_code:
        query = query.filter(TagExceptionTicket.tag_code == tag_code)
    if area:
        query = query.filter(TagExceptionTicket.area == area)
    if group_name:
        query = query.filter(TagExceptionTicket.group_name == group_name)
    if responsible_person:
        query = query.filter(TagExceptionTicket.responsible_person == responsible_person)
    if exception_type:
        try:
            et = ExceptionType(exception_type)
            query = query.filter(TagExceptionTicket.exception_type == et)
        except ValueError:
            raise BusinessError(
                f"无效的异常类型筛选值: {exception_type}",
                conflict_object=exception_type,
                code=400
            )
    if ticket_status:
        try:
            ts = TicketStatus(ticket_status)
            query = query.filter(TagExceptionTicket.ticket_status == ts)
        except ValueError:
            raise BusinessError(
                f"无效的处理状态筛选值: {ticket_status}",
                conflict_object=ticket_status,
                code=400
            )
    if start_date:
        query = query.filter(TagExceptionTicket.created_at >= start_date)
    if end_date:
        query = query.filter(TagExceptionTicket.created_at <= end_date)

    total = query.count()
    items = query.order_by(TagExceptionTicket.id.desc()).offset(skip).limit(limit).all()
    return items, total


def handle_exception_ticket(
    db: Session,
    ticket_id: int,
    handle_data: ExceptionTicketHandle
) -> TagExceptionTicket:
    ticket = get_exception_ticket(db, ticket_id)
    if not ticket:
        raise BusinessError(f"异常工单 ID {ticket_id} 不存在", code=404)

    if ticket.ticket_status == TicketStatus.CLOSED:
        raise BusinessError(
            f"异常工单 ID {ticket_id} 已闭环，不能重复处理",
            conflict_object=f"异常工单#{ticket_id}",
            current_status=ticket.ticket_status.value,
            code=409
        )

    try:
        target_status = TicketStatus(handle_data.ticket_status)
    except ValueError:
        raise BusinessError(
            f"无效的处理状态: {handle_data.ticket_status}",
            conflict_object=handle_data.ticket_status,
            code=400
        )

    now = datetime.utcnow()
    ticket.handling_conclusion = handle_data.handling_conclusion
    ticket.handler = handle_data.handler
    ticket.handling_time = now
    ticket.ticket_status = target_status
    ticket.updated_at = now

    if target_status == TicketStatus.CLOSED:
        tag = db.query(LuggageTag).filter(LuggageTag.id == ticket.tag_id).first()
        if tag and tag.status == TagStatus.PENDING_CHECK:
            other_unclosed = db.query(TagExceptionTicket).filter(
                and_(
                    TagExceptionTicket.tag_id == tag.id,
                    TagExceptionTicket.id != ticket.id,
                    TagExceptionTicket.ticket_status != TicketStatus.CLOSED
                )
            ).first()
            if not other_unclosed:
                tag.status = TagStatus.AVAILABLE
                tag.updated_at = now

    db.commit()
    db.refresh(ticket)
    return ticket


def get_exception_ticket_stats(db: Session) -> dict:
    pending_count = db.query(TagExceptionTicket).filter(
        TagExceptionTicket.ticket_status != TicketStatus.CLOSED
    ).count()

    closed_count = db.query(TagExceptionTicket).filter(
        TagExceptionTicket.ticket_status == TicketStatus.CLOSED
    ).count()

    by_responsible_records = db.query(
        TagExceptionTicket.responsible_person,
        func.sum(case(
            (TagExceptionTicket.ticket_status != TicketStatus.CLOSED, 1),
            else_=0
        )).label("unclosed_count"),
        func.count(TagExceptionTicket.id).label("total_count")
    ).group_by(TagExceptionTicket.responsible_person).all()

    by_responsible = []
    for person, unclosed, total in by_responsible_records:
        by_responsible.append({
            "responsible_person": person,
            "unclosed_count": int(unclosed or 0),
            "total_count": int(total or 0)
        })
    by_responsible.sort(key=lambda x: x["unclosed_count"], reverse=True)

    by_area_records = db.query(
        TagExceptionTicket.area,
        func.count(TagExceptionTicket.id).label("exception_count"),
        func.sum(case(
            (TagExceptionTicket.ticket_status != TicketStatus.CLOSED, 1),
            else_=0
        )).label("unclosed_count")
    ).group_by(TagExceptionTicket.area).all()

    by_area = []
    for area, exc_count, unclosed in by_area_records:
        by_area.append({
            "area": area,
            "exception_count": int(exc_count or 0),
            "unclosed_count": int(unclosed or 0)
        })
    by_area.sort(key=lambda x: x["exception_count"], reverse=True)

    return {
        "pending_count": pending_count,
        "closed_count": closed_count,
        "by_responsible": by_responsible,
        "by_area": by_area
    }


def get_exception_ticket_detail(db: Session, ticket_id: int) -> Optional[dict]:
    ticket = get_exception_ticket(db, ticket_id)
    if not ticket:
        return None

    tag = db.query(LuggageTag).filter(LuggageTag.id == ticket.tag_id).first()
    if not tag:
        raise BusinessError(f"寄物牌 ID {ticket.tag_id} 不存在", code=404)

    latest_issue_record = None
    if ticket.issue_record_id:
        latest_issue_record = db.query(TagIssueRecord).filter(
            TagIssueRecord.id == ticket.issue_record_id
        ).first()

    if not latest_issue_record:
        latest_issue_record = db.query(TagIssueRecord).filter(
            TagIssueRecord.tag_id == tag.id
        ).order_by(TagIssueRecord.id.desc()).first()

    check_record = None
    if latest_issue_record:
        check_record = db.query(TagCheckRecord).filter(
            TagCheckRecord.issue_record_id == latest_issue_record.id
        ).first()

    processing_progress = []
    processing_progress.append({
        "status": TicketStatus.PENDING.value,
        "handler": None,
        "handling_conclusion": None,
        "handling_time": None,
        "timestamp": ticket.created_at
    })

    if ticket.ticket_status in [TicketStatus.PROCESSING, TicketStatus.CLOSED]:
        processing_progress.append({
            "status": TicketStatus.PROCESSING.value,
            "handler": ticket.handler,
            "handling_conclusion": ticket.handling_conclusion,
            "handling_time": ticket.handling_time,
            "timestamp": ticket.handling_time if ticket.handling_time else ticket.updated_at
        })

    if ticket.ticket_status == TicketStatus.CLOSED:
        processing_progress.append({
            "status": TicketStatus.CLOSED.value,
            "handler": ticket.handler,
            "handling_conclusion": ticket.handling_conclusion,
            "handling_time": ticket.handling_time,
            "timestamp": ticket.handling_time if ticket.handling_time else ticket.updated_at
        })

    can_handle = ticket.ticket_status != TicketStatus.CLOSED

    return {
        "ticket": ticket,
        "tag_status": tag,
        "latest_issue_record": latest_issue_record,
        "check_record": check_record,
        "processing_progress": processing_progress,
        "current_responsible_person": tag.responsible_person,
        "can_handle": can_handle
    }


def get_exception_ticket_detailed_stats(db: Session) -> dict:
    total_count = db.query(TagExceptionTicket).count()
    pending_count = db.query(TagExceptionTicket).filter(
        TagExceptionTicket.ticket_status == TicketStatus.PENDING
    ).count()
    processing_count = db.query(TagExceptionTicket).filter(
        TagExceptionTicket.ticket_status == TicketStatus.PROCESSING
    ).count()
    closed_count = db.query(TagExceptionTicket).filter(
        TagExceptionTicket.ticket_status == TicketStatus.CLOSED
    ).count()

    total_pending = pending_count + processing_count
    closure_rate = round(closed_count / total_count * 100, 2) if total_count > 0 else 0.0

    overview = {
        "total_count": total_count,
        "pending_count": pending_count,
        "processing_count": processing_count,
        "total_pending": total_pending,
        "closed_count": closed_count,
        "closure_rate": closure_rate
    }

    by_area_records = db.query(
        TagExceptionTicket.area,
        func.count(TagExceptionTicket.id).label("total_count"),
        func.sum(case(
            (TagExceptionTicket.ticket_status == TicketStatus.CLOSED, 0),
            else_=1
        )).label("pending_count"),
        func.sum(case(
            (TagExceptionTicket.ticket_status == TicketStatus.CLOSED, 1),
            else_=0
        )).label("closed_count")
    ).group_by(TagExceptionTicket.area).all()

    by_area = []
    for area, total, pending, closed in by_area_records:
        closed_int = int(closed or 0)
        total_int = int(total or 0)
        rate = round(closed_int / total_int * 100, 2) if total_int > 0 else 0.0
        by_area.append({
            "area": area,
            "total_count": total_int,
            "pending_count": int(pending or 0),
            "closed_count": closed_int,
            "closure_rate": rate
        })
    by_area.sort(key=lambda x: x["total_count"], reverse=True)

    by_responsible_records = db.query(
        TagExceptionTicket.responsible_person,
        func.count(TagExceptionTicket.id).label("total_count"),
        func.sum(case(
            (TagExceptionTicket.ticket_status == TicketStatus.CLOSED, 0),
            else_=1
        )).label("pending_count"),
        func.sum(case(
            (TagExceptionTicket.ticket_status == TicketStatus.CLOSED, 1),
            else_=0
        )).label("closed_count")
    ).group_by(TagExceptionTicket.responsible_person).all()

    by_responsible = []
    for person, total, pending, closed in by_responsible_records:
        closed_int = int(closed or 0)
        total_int = int(total or 0)
        rate = round(closed_int / total_int * 100, 2) if total_int > 0 else 0.0
        by_responsible.append({
            "responsible_person": person,
            "total_count": total_int,
            "pending_count": int(pending or 0),
            "closed_count": closed_int,
            "closure_rate": rate
        })
    by_responsible.sort(key=lambda x: x["pending_count"], reverse=True)

    by_type_records = db.query(
        TagExceptionTicket.exception_type,
        func.count(TagExceptionTicket.id).label("total_count"),
        func.sum(case(
            (TagExceptionTicket.ticket_status == TicketStatus.CLOSED, 0),
            else_=1
        )).label("pending_count"),
        func.sum(case(
            (TagExceptionTicket.ticket_status == TicketStatus.CLOSED, 1),
            else_=0
        )).label("closed_count")
    ).group_by(TagExceptionTicket.exception_type).all()

    by_exception_type = []
    for ex_type, total, pending, closed in by_type_records:
        closed_int = int(closed or 0)
        total_int = int(total or 0)
        rate = round(closed_int / total_int * 100, 2) if total_int > 0 else 0.0
        by_exception_type.append({
            "exception_type": ex_type.value if isinstance(ex_type, ExceptionType) else str(ex_type),
            "total_count": total_int,
            "pending_count": int(pending or 0),
            "closed_count": closed_int,
            "closure_rate": rate
        })
    by_exception_type.sort(key=lambda x: x["total_count"], reverse=True)

    return {
        "overview": overview,
        "by_area": by_area,
        "by_responsible": by_responsible,
        "by_exception_type": by_exception_type
    }


def update_overtime_tags(db: Session):
    now = datetime.utcnow()
    overtime_tags = db.query(LuggageTag).filter(
        and_(
            LuggageTag.status == TagStatus.IN_USE,
            LuggageTag.expected_return_time < now
        )
    ).all()

    for tag in overtime_tags:
        tag.status = TagStatus.OVERTIME
        tag.updated_at = now

        latest_record = db.query(TagIssueRecord).filter(
            and_(
                TagIssueRecord.tag_id == tag.id,
                TagIssueRecord.status == "使用中"
            )
        ).order_by(TagIssueRecord.id.desc()).first()

        if latest_record:
            latest_record.is_overtime = 1
            overtime_delta = now - tag.expected_return_time
            latest_record.overtime_hours = int(overtime_delta.total_seconds() / 3600) + 1

            _auto_create_exception_ticket(
                db, tag, latest_record,
                ExceptionType.OVERTIME,
                f"寄物牌超时{latest_record.overtime_hours}小时未归还"
            )

    db.commit()
    return len(overtime_tags)
