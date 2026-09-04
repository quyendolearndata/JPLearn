import json
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from jplearn_api.alert import enqueue_alert
from jplearn_api.sanitizer import sanitize_message
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
            status_code = int(getattr(error, "status_code", 500))
            if status_code >= 500:
                error_class = error.__class__.__name__
                safe_msg = sanitize_message(f"{error_class}: {str(error)}")[:300]
                log_entry = {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "error_class": error_class,
                    "message": safe_msg,
                }
                print(json.dumps(log_entry))
                queue = getattr(request.app.state, "alert_queue", None)
                enqueue_alert(
                    self.settings,
                    method=request.method,
                    path=request.url.path,
                    status=500,
                    request_id=request_id,
                    message=safe_msg,
                    queue=queue,
                )
            raise
        response.headers["x-request-id"] = request_id
        if response.status_code >= 500:
            log_entry = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "message": f"http_{response.status_code}",
            }
            print(json.dumps(log_entry))
            queue = getattr(request.app.state, "alert_queue", None)
            enqueue_alert(
                self.settings,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                request_id=request_id,
                message=f"http_{response.status_code}",
                queue=queue,
            )
        return response
