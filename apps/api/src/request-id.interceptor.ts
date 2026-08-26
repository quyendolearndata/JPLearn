import {
  CallHandler,
  ExecutionContext,
  HttpException,
  Injectable,
  NestInterceptor,
} from "@nestjs/common";
import { randomUUID } from "node:crypto";
import { catchError, throwError } from "rxjs";
import { sendAlert5xx } from "./alert";

@Injectable()
export class RequestIdInterceptor implements NestInterceptor {
  intercept(ctx: ExecutionContext, next: CallHandler) {
    const res = ctx.switchToHttp().getResponse();
    const req = ctx.switchToHttp().getRequest<{
      method: string;
      path: string;
      headers: Record<string, string | undefined>;
      requestId?: string;
    }>();
    const id = String(req.headers["x-request-id"] ?? randomUUID());
    req.requestId = id;
    res.setHeader("x-request-id", id);
    return next.handle().pipe(
      catchError((err: unknown) => {
        const status = err instanceof HttpException ? err.getStatus() : 500;
        if (status >= 500) {
          const message = err instanceof Error ? err.message : "internal_error";
          console.error(
            JSON.stringify({
              request_id: id,
              status,
              message,
            }),
          );
          void sendAlert5xx({
            method: req.method,
            path: req.path,
            status,
            requestId: id,
            message,
          });
        }
        return throwError(() => err);
      }),
    );
  }
}
