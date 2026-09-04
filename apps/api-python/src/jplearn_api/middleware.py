from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from jplearn_api.alert import send_alert_5xx
from jplearn_api.settings import Settings


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception as error:
            if not getattr(error, "status_code", None) or int(getattr(error, "status_code")) >= 500:
                print(
                    '{"request_id":"%s","status":500,"message":"%s"}'
                    % (request_id, str(error).replace('"', "'")[:300]),
                )
                await send_alert_5xx(
                    self.settings,
                    method=request.method,
                    path=request.url.path,
                    status=500,
                    request_id=request_id,
                    message=str(error),
                )
            raise
        response.headers["x-request-id"] = request_id
        if response.status_code >= 500:
            print(
                '{"request_id":"%s","status":%s,"message":"http_%s"}'
                % (request_id, response.status_code, response.status_code),
            )
            await send_alert_5xx(
                self.settings,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                request_id=request_id,
                message=f"http_{response.status_code}",
            )
        return response
