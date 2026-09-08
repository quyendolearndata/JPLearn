from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request

NEST_ERROR_NAME = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    500: "Internal Server Error",
}


def nest_error_body(status_code: int, message: str | list[str]) -> dict:
    body: dict[str, object] = {
        "statusCode": status_code,
        "message": message,
    }
    # Nest only includes `error` when the exception carried one; bare
    # UnauthorizedException() yields just {statusCode, message}.
    if status_code != 401:
        body["error"] = NEST_ERROR_NAME.get(status_code, "Error")
    return body


def nest_error_response(
    status_code: int,
    message: str | list[str],
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=nest_error_body(status_code, message),
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    headers = dict(exc.headers) if exc.headers else None
    if exc.status_code == 404 and (exc.detail == "Not Found" or exc.detail == {}):
        return nest_error_response(404, f"Cannot {request.method} {request.url.path}", headers=headers)
    detail = exc.detail
    if isinstance(detail, list):
        message: str | list[str] = [str(item) for item in detail]
    else:
        message = str(detail)
    return nest_error_response(exc.status_code, message, headers=headers)


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    messages = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        messages.append(f"{loc}: {error.get('msg')}" if loc else str(error.get("msg")))
    return nest_error_response(400, messages if len(messages) > 1 else (messages[0] if messages else "Bad Request"))


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return nest_error_response(500, "Internal server error")
