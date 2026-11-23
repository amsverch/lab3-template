
from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Flight(Base):
    __tablename__ = "flights"

    flight_number = Column(String, primary_key=True, index=True)
    from_airport = Column(String, nullable=False)
    to_airport = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    price = Column(Float, nullable=False)
