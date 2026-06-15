from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TagBase(BaseModel):
    tag_code: str = Field(..., max_length=50, description="寄物牌编号")
    area: str = Field(..., max_length=100, description="所属区域")
    group_name: str = Field(..., max_length=100, description="分组")
    retention_hours: int = Field(default=24, gt=0, description="保留时长(小时)")
    responsible_person: str = Field(..., max_length=100, description="责任人")


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    area: Optional[str] = None
    group_name: Optional[str] = None
    retention_hours: Optional[int] = None
    responsible_person: Optional[str] = None


class TagStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None


class TagResponse(TagBase):
    id: int
    status: str
    current_user: Optional[str] = None
    issue_time: Optional[datetime] = None
    expected_return_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TagListResponse(BaseModel):
    items: List[TagResponse]
    total: int
    page: int
    page_size: int


class IssueRecordBase(BaseModel):
    user_name: str = Field(..., max_length=100, description="使用人")
    user_contact: Optional[str] = Field(None, max_length=100, description="使用人联系方式")


class IssueTagRequest(IssueRecordBase):
    tag_code: Optional[str] = None
    area: Optional[str] = None
    group_name: Optional[str] = None
    responsible_person: Optional[str] = None


class ReturnTagRequest(BaseModel):
    return_note: Optional[str] = None


class IssueRecordResponse(BaseModel):
    id: int
    tag_id: int
    tag_code: str
    area: str
    group_name: str
    responsible_person: str
    user_name: str
    user_contact: Optional[str] = None
    issue_time: datetime
    expected_return_time: datetime
    actual_return_time: Optional[datetime] = None
    is_overtime: int
    overtime_hours: int
    status: str
    return_note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class IssueRecordListResponse(BaseModel):
    items: List[IssueRecordResponse]
    total: int
    page: int
    page_size: int


class CheckRecordBase(BaseModel):
    overtime_description: str = Field(..., description="逾期说明")
    handling_conclusion: str = Field(..., description="处理结论")
    check_person: str = Field(..., max_length=100, description="核对人")
    is_closed: int = Field(default=1, description="是否闭环 0=未闭环 1=已闭环")


class CheckRecordCreate(CheckRecordBase):
    pass


class CheckRecordResponse(CheckRecordBase):
    id: int
    tag_id: int
    issue_record_id: int
    tag_code: str
    check_time: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class CheckRecordListResponse(BaseModel):
    items: List[CheckRecordResponse]
    total: int
    page: int
    page_size: int


class OvertimeAreaStats(BaseModel):
    area: str
    total_count: int
    overtime_count: int
    overtime_rate: float


class ResponsibleClosureStats(BaseModel):
    responsible_person: str
    total_checks: int
    closed_count: int
    closure_rate: float


class PendingCheckStats(BaseModel):
    pending_count: int
    pending_tags: List[TagResponse]


class StatisticsResponse(BaseModel):
    overtime_high_risk_areas: List[OvertimeAreaStats]
    responsible_closure_rates: List[ResponsibleClosureStats]
    pending_check_stats: PendingCheckStats


class AlertItem(BaseModel):
    alert_type: str
    alert_level: str
    target: str
    message: str
    details: dict


class AlertResponse(BaseModel):
    alerts: List[AlertItem]
    total: int


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    code: int
    message: str
    conflict_object: Optional[str] = None
    current_status: Optional[str] = None
