from datetime import datetime

from flight.database import SessionLocal
from flight.models import Flight


def seed_flights():
    db = SessionLocal()

    try:
        existing_flight = db.query(Flight).filter_by(
            flight_number="AFL031"
        ).first()

        if existing_flight is None:
            flight = Flight(
                flight_number="AFL031",
                from_airport="Санкт-Петербург Пулково",
                to_airport="Москва Шереметьево",
                date=datetime(2021, 10, 8, 20, 0),
                price=1500
            )

            db.add(flight)
            db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()