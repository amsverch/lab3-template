import uuid

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_uid = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_name = Column(String, nullable=False, index=True)

    flight_number = Column(String, nullable=False)
    from_airport = Column(String, nullable=False)
    to_airport = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="PAID")
