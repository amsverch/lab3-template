
import queue
import threading
import time
import os

import httpx
from fastapi import FastAPI, HTTPException, Query, Header, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gateway.circuit_breaker import CircuitBreaker


app = FastAPI(title="Gateway Service")


class TicketPurchaseRequest(BaseModel):
    flightNumber: str
    price: float
    paidFromBalance: bool


FLIGHT_SERVICE_URL = os.getenv(
    "FLIGHT_SERVICE_URL",
    "http://localhost:8051"
)

TICKET_SERVICE_URL = os.getenv(
    "TICKET_SERVICE_URL",
    "http://localhost:8071"
)

BONUS_SERVICE_URL = os.getenv(
    "BONUS_SERVICE_URL",
    "http://localhost:8052"
)

compensation_queue = queue.Queue()


# Отдельный Circuit Breaker для каждого сервиса.
flight_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
ticket_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
bonus_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)


def circuit_get(breaker, url, **kwargs):
    """Выполняет GET-запрос с защитой Circuit Breaker."""
    if not breaker.before_request():
        raise httpx.RequestError("Circuit Breaker is OPEN")

    try:
        response = httpx.get(url, **kwargs)

        if response.status_code >= 500:
            breaker.record_failure()
        else:
            # 404 означает, что сервис доступен, но ресурс не найден.
            breaker.record_success()

        response.raise_for_status()
        return response

    except httpx.RequestError:
        breaker.record_failure()
        raise


def enrich_tickets(tickets):
    """Дополняет билеты данными Flight; при сбое использует fallback."""
    try:
        response = circuit_get(
            flight_breaker,
            f"{FLIGHT_SERVICE_URL}/api/v1/flights",
            params={"page": 1, "size": 100},
            timeout=5.0
        )
        flights = response.json().get("items", [])
        flights_by_number = {
            flight["flightNumber"]: flight
            for flight in flights
        }

    except (httpx.RequestError, httpx.HTTPStatusError, KeyError, ValueError):
        flights_by_number = {}

    enriched = []

    for ticket in tickets:
        ticket = dict(ticket)
        flight = flights_by_number.get(ticket.get("flightNumber"))

        ticket["fromAirport"] = (
            flight.get("fromAirport", "Unknown")
            if flight else "Unknown"
        )
        ticket["toAirport"] = (
            flight.get("toAirport", "Unknown")
            if flight else "Unknown"
        )
        ticket["date"] = (
            flight.get("date", "")
            if flight else ""
        )

        enriched.append(ticket)

    return enriched


def process_compensation_queue():
    while True:
        task = compensation_queue.get()

        while True:
            try:
                response = httpx.post(
                    f"{BONUS_SERVICE_URL}/privilege/compensate",
                    json=task,
                    timeout=10.0
                )

                if response.status_code in (408, 429) or response.status_code >= 500:
                    print(
                        f"Temporary Bonus Service error "
                        f"{response.status_code}. Retrying..."
                    )
                    time.sleep(1)
                    continue

                response.raise_for_status()

                print(
                    f"Compensation processed: "
                    f"{task['ticketUid']}"
                )
                break

            except httpx.RequestError as error:
                print(
                    f"Bonus Service unavailable: {error}. Retrying..."
                )
                time.sleep(1)

            except httpx.HTTPStatusError as error:
                print(
                    f"Permanent compensation error: "
                    f"{error.response.status_code} "
                    f"for ticket {task['ticketUid']}"
                )
                break

        compensation_queue.task_done()


@app.on_event("startup")
def start_compensation_worker():
    worker = threading.Thread(
        target=process_compensation_queue,
        daemon=True
    )
    worker.start()


@app.get("/manage/health")
def health():
    return {"status": "OK"}


@app.get("/api/v1/flights")
def get_flights(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100)
):
    try:
        response = circuit_get(
            flight_breaker,
            f"{FLIGHT_SERVICE_URL}/api/v1/flights",
            params={"page": page, "size": size},
            timeout=5.0
        )
        return response.json()

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=error.response.status_code,
            detail="Flight Service error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Flight Service unavailable"
        )


@app.get("/api/v1/tickets")
def get_tickets(
    user_name: str = Header(..., alias="X-User-Name")
):
    try:
        response = circuit_get(
            ticket_breaker,
            f"{TICKET_SERVICE_URL}/tickets",
            headers={"X-User-Name": user_name},
            timeout=5.0
        )
        tickets = response.json()
        return enrich_tickets(tickets)

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=error.response.status_code,
            detail="Ticket Service error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Ticket Service unavailable"
        )


@app.get("/api/v1/tickets/{ticket_uid}")
def get_ticket(
    ticket_uid: str,
    user_name: str = Header(..., alias="X-User-Name")
):
    try:
        response = circuit_get(
            ticket_breaker,
            f"{TICKET_SERVICE_URL}/tickets/{ticket_uid}",
            headers={"X-User-Name": user_name},
            timeout=5.0
        )
        ticket = response.json()
        enriched = enrich_tickets([ticket])
        return enriched[0]

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=error.response.status_code,
            detail="Ticket Service error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Ticket Service unavailable"
        )


@app.get("/api/v1/privilege")
def get_privilege(
    user_name: str = Header(..., alias="X-User-Name")
):
    try:
        response = circuit_get(
            bonus_breaker,
            f"{BONUS_SERVICE_URL}/privilege",
            headers={"X-User-Name": user_name},
            timeout=5.0
        )
        return response.json()

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=error.response.status_code,
            detail="Bonus Service error"
        )

    except httpx.RequestError:
        return JSONResponse(
            status_code=503,
            content={"message": "Bonus Service unavailable"}
        )


@app.get("/api/v1/me")
def get_me(
    user_name: str = Header(..., alias="X-User-Name")
):
    headers = {"X-User-Name": user_name}

    # Ticket — критический источник.
    try:
        tickets_response = circuit_get(
            ticket_breaker,
            f"{TICKET_SERVICE_URL}/tickets",
            headers=headers,
            timeout=5.0
        )
        tickets = tickets_response.json()
        tickets = enrich_tickets(tickets)

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Ticket Service unavailable"
        )

    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=500,
            detail="Ticket Service error"
        )

    # Bonus — необязательный источник.
    try:
        privilege_response = circuit_get(
            bonus_breaker,
            f"{BONUS_SERVICE_URL}/privilege",
            headers=headers,
            timeout=5.0
        )
        privilege_data = privilege_response.json()

        privilege = {
            "balance": privilege_data["balance"],
            "status": privilege_data["status"]
        }

    except (httpx.RequestError, httpx.HTTPStatusError, KeyError, ValueError):
        privilege = {}

    return {
        "tickets": tickets,
        "privilege": privilege
    }


@app.post("/api/v1/tickets")
def buy_ticket(
    request: TicketPurchaseRequest,
    user_name: str = Header(..., alias="X-User-Name")
):
    headers = {"X-User-Name": user_name}

    # 1. Получаем информацию о рейсах.
    try:
        flights_response = circuit_get(
            flight_breaker,
            f"{FLIGHT_SERVICE_URL}/api/v1/flights",
            params={"page": 1, "size": 100},
            timeout=5.0
        )
        flights = flights_response.json()["items"]

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Flight Service unavailable"
        )

    except (httpx.HTTPStatusError, KeyError):
        raise HTTPException(
            status_code=503,
            detail="Flight Service error"
        )

    # 2. Находим нужный рейс.
    flight = next(
        (
            item for item in flights
            if item["flightNumber"] == request.flightNumber
        ),
        None
    )

    if flight is None:
        raise HTTPException(
            status_code=404,
            detail="Flight not found"
        )

    if request.price != flight["price"]:
        raise HTTPException(
            status_code=400,
            detail="Incorrect flight price"
        )

    # 3. Создаём билет.
    try:
        ticket_response = httpx.post(
            f"{TICKET_SERVICE_URL}/tickets",
            headers=headers,
            json=flight,
            timeout=5.0
        )
        ticket_response.raise_for_status()
        ticket = ticket_response.json()

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Ticket Service unavailable"
        )

    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=503,
            detail="Ticket Service error"
        )

    # 4. Начисляем или списываем бонусы.
    bonus_operation = {
        "userName": user_name,
        "ticketUid": ticket["ticketUid"],
        "amount": (
            flight["price"]
            if request.paidFromBalance
            else flight["price"] * 0.1
        )
    }

    bonus_endpoint = (
        "/privilege/debit"
        if request.paidFromBalance
        else "/privilege/accrue"
    )

    try:
        bonus_response = httpx.post(
            f"{BONUS_SERVICE_URL}{bonus_endpoint}",
            json=bonus_operation,
            timeout=5.0
        )
        bonus_response.raise_for_status()
        privilege = bonus_response.json()

    except (httpx.RequestError, httpx.HTTPStatusError):
        # При сбое Bonus Service удаляем созданный билет.
        try:
            rollback_response = httpx.delete(
                f"{TICKET_SERVICE_URL}/tickets/{ticket['ticketUid']}",
                headers=headers,
                timeout=5.0
            )
            rollback_response.raise_for_status()

        except (httpx.RequestError, httpx.HTTPStatusError) as error:
            print(f"Ticket rollback failed: {error}")

        return JSONResponse(
            status_code=503,
            content={"message": "Bonus Service unavailable"}
        )

    # 5. Формируем ответ клиенту.
    return {
        **ticket,
        "paidByMoney": 0 if request.paidFromBalance else flight["price"],
        "paidByBonuses": flight["price"] if request.paidFromBalance else 0,
        "privilege": privilege
    }


@app.delete("/api/v1/tickets/{ticket_uid}", status_code=204)
def cancel_ticket(
    ticket_uid: str,
    user_name: str = Header(..., alias="X-User-Name")
):
    headers = {"X-User-Name": user_name}

    # 1. Получаем билет и проверяем, что он принадлежит пользователю.
    try:
        ticket_response = circuit_get(
            ticket_breaker,
            f"{TICKET_SERVICE_URL}/tickets/{ticket_uid}",
            headers=headers,
            timeout=5.0
        )
        ticket_response.raise_for_status()
        ticket = ticket_response.json()

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=error.response.status_code,
            detail="Ticket not found"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Ticket Service unavailable"
        )

    # 2. Меняем статус билета на CANCELED.
    if ticket["status"] != "CANCELED":
        try:
            cancel_response = httpx.post(
                f"{TICKET_SERVICE_URL}/tickets/{ticket_uid}/cancel",
                headers=headers,
                timeout=5.0
            )
            cancel_response.raise_for_status()

        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Ticket Service unavailable"
            )

        except httpx.HTTPStatusError:
            raise HTTPException(
                status_code=500,
                detail="Ticket cancellation failed"
            )

    # 3. Компенсируем бонусную операцию.
    try:
        httpx.post(
            f"{BONUS_SERVICE_URL}/privilege/compensate",
            json={
                "userName": user_name,
                "ticketUid": ticket_uid,
                "amount": ticket["price"]
            },
            timeout=5.0
        ).raise_for_status()

    except (httpx.RequestError, httpx.HTTPStatusError):
        compensation_queue.put({
            "userName": user_name,
            "ticketUid": ticket_uid,
            "amount": ticket["price"]
        })

    return Response(status_code=204)
