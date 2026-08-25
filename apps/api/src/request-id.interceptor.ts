import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from "@nestjs/common";
import { randomUUID } from "node:crypto";
import { catchError, throwError } from "rxjs";

@Injectable()
export class RequestIdInterceptor implements NestInterceptor {
  intercept(ctx: ExecutionContext, next: CallHandler) {
    const res = ctx.switchToHttp().getResponse();
    const req = ctx.switchToHttp().getRequest<{
      headers: Record<string, string | undefined>;
      requestId?: string;
    }>();
    const id = String(req.headers["x-request-id"] ?? randomUUID());
    req.requestId = id;
    res.setHeader("x-request-id", id);
    return next.handle().pipe(
      catchError((err: { status?: number; message?: string }) => {
        const status = err.status ?? 500;
        if (status >= 500) {
          console.error(
            JSON.stringify({
              request_id: id,
              status,
              message: err.message ?? "internal_error",
            }),
          );
        }
        return throwError(() => err);
      }),
    );
  }
}
