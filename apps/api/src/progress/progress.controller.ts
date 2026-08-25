import { Controller, Get, Req, UseGuards } from "@nestjs/common";
import { JwtGuard, type AuthenticatedRequest } from "../auth/jwt.guard";
import { SessionsService } from "../sessions/sessions.service";

@Controller("progress")
@UseGuards(JwtGuard)
export class ProgressController {
  constructor(private readonly sessions: SessionsService) {}

  @Get()
  get(@Req() request: AuthenticatedRequest) {
    return this.sessions.progress(request.user.id);
  }
}
