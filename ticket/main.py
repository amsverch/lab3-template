from datetime import datetime

from fastapi import Depends, FastAPI, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ticket.database import engine, get_db
from ticket.models import Base, Ticket


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ticket Service")


class TicketCreateRequest(BaseModel):
    flightNumber: str
    fromAirport: str
    toAirport: str
    date: datetime
    price: float


@app.get("/manage/health")
def health():
    return {"status": "OK"}

@app.get("/tickets")
def get_tickets(
    user_name: str = Header(..., alias="X-User-Name"),
    db: Session = Depends(get_db)
):
    tickets = (
        db.query(Ticket)
        .filter(Ticket.user_name == user_name)
        .all()
    )

    return [
        {
            "ticketUid": str(ticket.ticket_uid),
            "flightNumber": ticket.flight_number,
            "fromAirport": ticket.from_airport,
            "toAirport": ticket.to_airport,
            "date": ticket.date.strftime("%Y-%m-%d %H:%M"),
            "price": ticket.price,
            "status": ticket.status
        }
        for ticket in tickets
    ]

@app.get("/tickets/{ticket_uid}")
def get_ticket(
    ticket_uid: str,
    user_name: str = Header(..., alias="X-User-Name"),
    db: Session = Depends(get_db)
):
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.ticket_uid == ticket_uid,
            Ticket.user_name == user_name
        )
        .first()
    )

    if ticket is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    return {
        "ticketUid": str(ticket.ticket_uid),
        "flightNumber": ticket.flight_number,
        "fromAirport": ticket.from_airport,
        "toAirport": ticket.to_airport,
        "date": ticket.date.strftime("%Y-%m-%d %H:%M"),
        "price": ticket.price,
        "status": ticket.status
    }

@app.delete("/tickets/{ticket_uid}")
def delete_ticket(
    ticket_uid: str,
    user_name: str = Header(..., alias="X-User-Name"),
    db: Session = Depends(get_db)
):
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.ticket_uid == ticket_uid,
            Ticket.user_name == user_name
        )
        .first()
    )

    if ticket is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    db.delete(ticket)
    db.commit()

    return {"detail": "Ticket deleted"}

@app.post("/tickets/{ticket_uid}/cancel")
def cancel_ticket(
    ticket_uid: str,
    user_name: str = Header(..., alias="X-User-Name"),
    db: Session = Depends(get_db)
):
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.ticket_uid == ticket_uid,
            Ticket.user_name == user_name
        )
        .first()
    )

    if ticket is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if ticket.status == "CANCELED":
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="Ticket already canceled"
        )

    ticket.status = "CANCELED"
    db.commit()
    db.refresh(ticket)

    return {
        "ticketUid": str(ticket.ticket_uid),
        "flightNumber": ticket.flight_number,
        "fromAirport": ticket.from_airport,
        "toAirport": ticket.to_airport,
        "date": ticket.date.strftime("%Y-%m-%d %H:%M"),
        "price": ticket.price,
        "status": ticket.status
    }

@app.post("/tickets")
def create_ticket(
    request: TicketCreateRequest,
    user_name: str = Header(..., alias="X-User-Name"),
    db: Session = Depends(get_db)
):
    ticket = Ticket(
        user_name=user_name,
        flight_number=request.flightNumber,
        from_airport=request.fromAirport,
        to_airport=request.toAirport,
        date=request.date,
        price=request.price,
        status="PAID"
    )

    try:
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
    except Exception:
        db.rollback()
        raise

    return {
        "ticketUid": str(ticket.ticket_uid),
        "flightNumber": ticket.flight_number,
        "fromAirport": ticket.from_airport,
        "toAirport": ticket.to_airport,
        "date": ticket.date.strftime("%Y-%m-%d %H:%M"),
        "price": ticket.price,
        "status": ticket.status
    }