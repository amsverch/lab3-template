from datetime import datetime
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel

from fastapi import Depends, FastAPI, Header
from sqlalchemy.orm import Session

from bonus.database import engine, get_db
from bonus.models import Base, Privilege, PrivilegeHistory


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bonus Service")
class BonusOperationRequest(BaseModel):
    userName: str
    ticketUid: UUID
    amount: float

@app.get("/manage/health")
def health():
    return {"status": "OK"}


@app.get("/privilege")
def get_privilege(
    user_name: str = Header(..., alias="X-User-Name"),
    db: Session = Depends(get_db)
):
    privilege = db.query(Privilege).filter(
        Privilege.user_name == user_name
    ).first()

    if privilege is None:
        privilege = Privilege(
            user_name=user_name,
            balance=0,
            status="BRONZE"
        )
        db.add(privilege)
        db.commit()
        db.refresh(privilege)

    history = (
        db.query(PrivilegeHistory)
        .filter(PrivilegeHistory.user_name == user_name)
        .order_by(PrivilegeHistory.date.desc())
        .all()
    )

    return {
        "balance": privilege.balance,
        "status": privilege.status,
        "history": [
            {
                "date": item.date.isoformat(),
                "balanceDiff": item.balance_diff,
                "ticketUid": str(item.ticket_uid),
                "operationType": item.operation_type
            }
            for item in history
        ]
    }

@app.post("/privilege/accrue")
def accrue_bonus(
    request: BonusOperationRequest,
    db: Session = Depends(get_db)
):
    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be positive"
        )

    privilege = db.query(Privilege).filter(
        Privilege.user_name == request.userName
    ).first()

    if privilege is None:
        privilege = Privilege(
            user_name=request.userName,
            balance=0,
            status="BRONZE"
        )
        db.add(privilege)
        db.flush()

    privilege.balance += request.amount

    history = PrivilegeHistory(
        user_name=request.userName,
        ticket_uid=request.ticketUid,
        date=datetime.utcnow(),
        balance_diff=request.amount,
        operation_type="FILLED_BY_MONEY"
    )

    db.add(history)
    db.commit()

    return {
        "balance": privilege.balance,
        "status": privilege.status
    }


@app.post("/privilege/debit")
def debit_bonus(
    request: BonusOperationRequest,
    db: Session = Depends(get_db)
):
    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be positive"
        )

    privilege = db.query(Privilege).filter(
        Privilege.user_name == request.userName
    ).first()

    if privilege is None or privilege.balance < request.amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient bonus balance"
        )

    privilege.balance -= request.amount

    history = PrivilegeHistory(
        user_name=request.userName,
        ticket_uid=request.ticketUid,
        date=datetime.utcnow(),
        balance_diff=-request.amount,
        operation_type="DEBIT_THE_ACCOUNT"
    )

    db.add(history)
    db.commit()

    return {
        "balance": privilege.balance,
        "status": privilege.status
    }

@app.post("/privilege/compensate")
def compensate_bonus(
    request: BonusOperationRequest,
    db: Session = Depends(get_db)
):
    privilege = db.query(Privilege).filter(
        Privilege.user_name == request.userName
    ).with_for_update().first()

    if privilege is None:
        raise HTTPException(
            status_code=404,
            detail="Privilege not found"
        )

    operations = (
        db.query(PrivilegeHistory)
        .filter(
            PrivilegeHistory.user_name == request.userName,
            PrivilegeHistory.ticket_uid == request.ticketUid
        )
        .order_by(PrivilegeHistory.date.asc())
        .all()
    )

    if not operations:
        raise HTTPException(
            status_code=404,
            detail="Original bonus operation not found"
        )

    original = next(
        (
            operation for operation in operations
            if operation.operation_type in (
                "FILLED_BY_MONEY",
                "DEBIT_THE_ACCOUNT"
            )
        ),
        None
    )

    if original is None:
        raise HTTPException(
            status_code=400,
            detail="Original bonus operation not found"
        )

    if original.operation_type == "FILLED_BY_MONEY":
        balance_diff = -original.balance_diff
        operation_type = "DEBIT_THE_ACCOUNT"

    else:
        balance_diff = -original.balance_diff
        operation_type = "FILL_IN_BALANCE"

    already_compensated = any(
        operation.operation_type == operation_type
        and abs(operation.balance_diff - balance_diff) < 1e-9
        for operation in operations
    )

    if already_compensated:
        return {
            "balance": privilege.balance,
            "status": privilege.status,
            "detail": "Already compensated"
        }

    privilege.balance += balance_diff

    compensation = PrivilegeHistory(
        user_name=request.userName,
        ticket_uid=request.ticketUid,
        date=datetime.utcnow(),
        balance_diff=balance_diff,
        operation_type=operation_type
    )

    db.add(compensation)
    db.commit()

    return {
        "balance": privilege.balance,
        "status": privilege.status
    }
