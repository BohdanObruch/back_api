from __future__ import annotations

import json
import os
from datetime import date, datetime
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError


DATE_FORMAT = "%d.%m.%Y"


class UserPayload(BaseModel):
    name: str = Field(alias="Name")
    surname: str = Field(alias="Surname")
    date_of_birth: str = Field(alias="DateOfBirth")
    interests: list[str] = Field(alias="Interests")

    model_config = {"populate_by_name": True}


class UserResponse(UserPayload):
    user_id: int = Field(alias="Id")
    age: int = Field(alias="Age")
    is_adult: bool = Field(alias="IsAdult")


app = FastAPI(
    title="User Management API",
    version="1.0.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

_users: dict[int, dict] = {}
_next_id = 1
_lock = Lock()


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="DateOfBirth must use dd.mm.yyyy format",
        ) from exc


def _calculate_age(date_of_birth: str) -> int:
    birth_date = _parse_date(date_of_birth).date()
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def _serialize_user(user_id: int, payload: UserPayload) -> dict:
    age = _calculate_age(payload.date_of_birth)
    return {
        "Id": user_id,
        "Name": payload.name,
        "Surname": payload.surname,
        "DateOfBirth": payload.date_of_birth,
        "Age": age,
        "IsAdult": age >= 18,
        "Interests": payload.interests,
    }


def _get_user_or_404(user_id: int) -> dict:
    user = _users.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


async def _read_payload(request: Request) -> UserPayload:
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(status_code=400, detail="Request body is required")

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    try:
        return UserPayload.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/api/user/create", response_model=UserResponse, response_model_by_alias=True)
async def create_user(request: Request) -> dict:
    global _next_id

    payload = await _read_payload(request)
    with _lock:
        user_id = _next_id
        _next_id += 1
        user = _serialize_user(user_id, payload)
        _users[user_id] = user

    return user


@app.get("/api/user/id/{user_id}", response_model=UserResponse, response_model_by_alias=True)
def get_user_by_id(user_id: int) -> dict:
    return _get_user_or_404(user_id)


@app.get(
    "/api/user/name/{user_name}",
    response_model=list[UserResponse],
    response_model_by_alias=True,
)
def get_users_by_name(user_name: str) -> list[dict]:
    return [
        user
        for user in _users.values()
        if user["Name"].lower() == user_name.lower()
    ]


@app.put("/api/user/update/{user_id}", response_model=UserResponse, response_model_by_alias=True)
async def update_user(user_id: int, request: Request) -> dict:
    _get_user_or_404(user_id)
    payload = await _read_payload(request)

    with _lock:
        user = _serialize_user(user_id, payload)
        _users[user_id] = user

    return user


@app.delete("/api/user/delete/{user_id}")
def delete_user(user_id: int) -> dict:
    with _lock:
        _get_user_or_404(user_id)
        del _users[user_id]

    return {"Message": f"User {user_id} deleted"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
