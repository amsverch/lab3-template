
from fastapi import Depends, FastAPI, Query
from sqlalchemy.orm import Session

from flight.database import engine, get_db
from flight.models import Base, Flight
from flight.seed import seed_flights

Base.metadata.create_all(bind=engine)
seed_flights()

app = FastAPI(title="Flight Service")


@app.get("/manage/health")
def health():
    return {"status": "OK"}


@app.get("/api/v1/flights")
def get_flights(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    total_elements = db.query(Flight).count()

    flights = (
        db.query(Flight)
        .order_by(Flight.flight_number)
        .offset(max(page - 1, 0) * size)
        .limit(size)
        .all()
    )

    return {
        "page": page,
        "pageSize": size,
        "totalElements": total_elements,
        "items": [
            {
                "flightNumber": flight.flight_number,
                "fromAirport": flight.from_airport,
                "toAirport": flight.to_airport,
                "date": flight.date.strftime("%Y-%m-%d %H:%M"),
                "price": flight.price
            }
            for flight in flights
        ]
    }
