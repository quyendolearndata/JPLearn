import {
  BadRequestException,
  Body,
  Controller,
  HttpCode,
  Param,
  Post,
  Req,
  UseGuards,
} from "@nestjs/common";
import type { DeviceClass } from "@jplearn/domain";
import { JwtGuard, type AuthenticatedRequest } from "../auth/jwt.guard";
import { SessionsService } from "./sessions.service";

@Controller("sessions")
@UseGuards(JwtGuard)
export class SessionsController {
  constructor(private readonly sessions: SessionsService) {}

  @Post()
  start(@Req() request: AuthenticatedRequest, @Body() body: { device_class?: DeviceClass }) {
    if (!body || !["web", "phone", "ipad"].includes(body.device_class ?? "")) {
      throw new BadRequestException("device_class is required");
    }
    return this.sessions.start(request.user.id, body.device_class as DeviceClass);
  }

  @Post(":id/end")
  @HttpCode(200)
  end(@Req() request: AuthenticatedRequest, @Param("id") id: string) {
    return this.sessions.end(request.user.id, id);
  }
}
