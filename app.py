from __future__ import annotations

import os
from datetime import date, datetime
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


DATE_FORMAT = "%d.%m.%Y"


class UserPayload(BaseModel):
    name: str = Field(alias="Name")
    surname: str = Field(alias="Surname")
    date_of_birth: str = Field(alias="DateOfBirth")
    interests: list[str] = Field(alias="Interests")

    model_config = {"populate_by_name": True}


class UserResponse(BaseModel):
    user_id: int = Field(alias="Id")
    name: str = Field(alias="Name")
    surname: str = Field(alias="Surname")
    date_of_birth: str = Field(alias="DateOfBirth")
    age: int = Field(alias="Age")
    is_adult: bool = Field(alias="IsAdult")
    interests: list[str] = Field(alias="Interests")

    model_config = {"populate_by_name": True}


app = FastAPI(
    title="User management system API",
    description="API that handles user management",
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


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"message": exc.errors()})


@app.get("/health", include_in_schema=False)
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post(
    "/api/user/create",
    summary="Create a user",
    response_model=UserResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "User created"},
        400: {"description": "Bad request"},
    },
)
async def create_user(payload: UserPayload) -> dict:
    global _next_id

    with _lock:
        user_id = _next_id
        _next_id += 1
        user = _serialize_user(user_id, payload)
        _users[user_id] = user

    return user


@app.get(
    "/api/user/id/{id}",
    summary="Get user by ID",
    response_model=UserResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "User found"},
        404: {"description": "User not found"},
    },
)
def get_user_by_id(id: int) -> dict:
    return _get_user_or_404(id)


@app.get(
    "/api/user/name/{name}",
    summary="Get users by name",
    response_model=list[UserResponse],
    response_model_by_alias=True,
    responses={200: {"description": "Success"}},
)
def get_users_by_name(name: str) -> list[dict]:
    return [
        user
        for user in _users.values()
        if user["Name"].lower() == name.lower()
    ]


@app.put(
    "/api/user/update/{id}",
    summary="Update a user by ID",
    response_model=UserResponse,
    response_model_by_alias=True,
    responses={200: {"description": "Success"}},
)
async def update_user(id: int, payload: UserPayload) -> dict:
    _get_user_or_404(id)

    with _lock:
        user = _serialize_user(id, payload)
        _users[id] = user

    return user


@app.delete(
    "/api/user/delete/{id}",
    summary="Delete a user by ID",
    status_code=200,
    responses={
        200: {"description": "Success"},
        400: {"description": "Incorrect id format"},
        404: {"description": "User not found"},
    },
)
def delete_user(id: int) -> Response:
    with _lock:
        _get_user_or_404(id)
        del _users[id]

    return Response(status_code=200)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    response_overrides = {
        "/api/user/create": {"200", "400"},
        "/api/user/id/{id}": {"200", "404"},
        "/api/user/name/{name}": {"200"},
        "/api/user/update/{id}": {"200"},
        "/api/user/delete/{id}": {"200", "400", "404"},
    }

    for path, allowed_codes in response_overrides.items():
        for operation in openapi_schema["paths"].get(path, {}).values():
            responses = operation.get("responses", {})
            for status_code in list(responses):
                if status_code not in allowed_codes:
                    del responses[status_code]

    create_operation = openapi_schema["paths"].get("/api/user/create", {}).get("post")
    if create_operation is not None:
        create_operation["responses"] = {
            "200": {
                "description": "User created",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/UserResponse"}
                    }
                },
            },
            "400": {"description": "Bad request"},
        }

    get_by_id_operation = openapi_schema["paths"].get("/api/user/id/{id}", {}).get("get")
    if get_by_id_operation is not None:
        get_by_id_operation["responses"] = {
            "200": {
                "description": "User found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/UserResponse"}
                    }
                },
            },
            "404": {"description": "User not found"},
        }

    get_by_name_operation = openapi_schema["paths"].get("/api/user/name/{name}", {}).get("get")
    if get_by_name_operation is not None:
        get_by_name_operation["responses"] = {
            "200": {
                "description": "Success",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/UserResponse"},
                        }
                    }
                },
            }
        }

    update_operation = openapi_schema["paths"].get("/api/user/update/{id}", {}).get("put")
    if update_operation is not None:
        update_operation["responses"] = {
            "200": {
                "description": "Success",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/UserResponse"}
                    }
                },
            }
        }

    delete_operation = openapi_schema["paths"].get("/api/user/delete/{id}", {}).get("delete")
    if delete_operation is not None:
        delete_operation["responses"] = {
            "200": {"description": "Success"},
            "400": {"description": "Incorrect id format"},
            "404": {"description": "User not found"},
        }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
