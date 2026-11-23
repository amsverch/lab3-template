import uuid

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Privilege(Base):
    __tablename__ = "privileges"

    user_name = Column(String, primary_key=True, index=True)
    balance = Column(Float, nullable=False, default=0)
    status = Column(String, nullable=False, default="BRONZE")


class PrivilegeHistory(Base):
    __tablename__ = "privilege_history"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_name = Column(String, nullable=False, index=True)
    ticket_uid = Column(UUID(as_uuid=True), nullable=False)
    date = Column(DateTime, nullable=False)
    balance_diff = Column(Float, nullable=False)
    operation_type = Column(String, nullable=False)