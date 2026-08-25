import {
  Body,
  Controller,
  Get,
  HttpCode,
  Inject,
  Post,
  Req,
  UseGuards,
} from "@nestjs/common";
import { AuthService } from "./auth.service";
import type { AuthCredentials } from "./dto";
import { JwtGuard, AuthenticatedRequest } from "./jwt.guard";

@Controller()
export class AuthController {
  constructor(@Inject(AuthService) private readonly auth: AuthService) {}

  @Post("auth/register")
  register(@Body() body: AuthCredentials) {
    return this.auth.register(body);
  }

  @Post("auth/login")
  @HttpCode(200)
  login(@Body() body: AuthCredentials) {
    return this.auth.login(body);
  }

  @Post("auth/logout")
  @HttpCode(204)
  @UseGuards(JwtGuard)
  async logout(@Req() request: AuthenticatedRequest): Promise<void> {
    await this.auth.logout(request.user.id);
  }

  @Get("me")
  @UseGuards(JwtGuard)
  me(@Req() request: AuthenticatedRequest) {
    return request.user;
  }
}
