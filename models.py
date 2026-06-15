import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from database import Base


class TagStatus(str, enum.Enum):
    PENDING_ISSUE = "待发放"
    IN_USE = "使用中"
    OVERTIME = "超时占用"
    PENDING_CHECK = "待核对"
    AVAILABLE = "恢复可用"
    DISABLED = "停用"


class LuggageTag(Base):
    __tablename__ = "luggage_tags"

    id = Column(Integer, primary_key=True, index=True)
    tag_code = Column(String(50), unique=True, index=True, nullable=False)
    area = Column(String(100), index=True, nullable=False)
    group_name = Column(String(100), index=True, nullable=False)
    retention_hours = Column(Integer, nullable=False, default=24)
    responsible_person = Column(String(100), index=True, nullable=False)
    status = Column(Enum(TagStatus), default=TagStatus.PENDING_ISSUE, index=True)
    current_user = Column(String(100), nullable=True)
    issue_time = Column(DateTime, nullable=True)
    expected_return_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    issue_records = relationship("TagIssueRecord", back_populates="tag", cascade="all, delete-orphan")
    check_records = relationship("TagCheckRecord", back_populates="tag", cascade="all, delete-orphan")


class TagIssueRecord(Base):
    __tablename__ = "tag_issue_records"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("luggage_tags.id"), nullable=False)
    tag_code = Column(String(50), index=True, nullable=False)
    area = Column(String(100), index=True, nullable=False)
    group_name = Column(String(100), index=True, nullable=False)
    responsible_person = Column(String(100), index=True, nullable=False)
    user_name = Column(String(100), nullable=False)
    user_contact = Column(String(100), nullable=True)
    issue_time = Column(DateTime, default=datetime.utcnow, index=True)
    expected_return_time = Column(DateTime, nullable=False)
    actual_return_time = Column(DateTime, nullable=True)
    is_overtime = Column(Integer, default=0, index=True)
    overtime_hours = Column(Integer, default=0)
    status = Column(String(50), default="使用中", index=True)
    return_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tag = relationship("LuggageTag", back_populates="issue_records")
    check_record = relationship("TagCheckRecord", back_populates="issue_record", uselist=False, cascade="all, delete-orphan")


class TagCheckRecord(Base):
    __tablename__ = "tag_check_records"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("luggage_tags.id"), nullable=False)
    issue_record_id = Column(Integer, ForeignKey("tag_issue_records.id"), nullable=False)
    tag_code = Column(String(50), index=True, nullable=False)
    overtime_description = Column(Text, nullable=False)
    handling_conclusion = Column(Text, nullable=False)
    check_person = Column(String(100), nullable=False)
    check_time = Column(DateTime, default=datetime.utcnow, index=True)
    is_closed = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tag = relationship("LuggageTag", back_populates="check_records")
    issue_record = relationship("TagIssueRecord", back_populates="check_record")
