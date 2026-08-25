import {
  Body,
  Controller,
  Get,
  Patch,
  Req,
  UseGuards,
} from "@nestjs/common";
import { JwtGuard, type AuthenticatedRequest } from "../auth/jwt.guard";
import { Roles } from "../auth/roles.decorator";
import { RolesGuard } from "../auth/roles.guard";
import { FlagsService, type Flags } from "./flags.service";

@Controller()
export class FlagsController {
  constructor(private readonly flags: FlagsService) {}

  @Get("flags")
  @UseGuards(JwtGuard)
  get(@Req() _request: AuthenticatedRequest): Promise<Flags> {
    return this.flags.get();
  }

  @Patch("staff/flags")
  @Roles("admin")
  @UseGuards(JwtGuard, RolesGuard)
  update(@Body() body: Flags): Promise<Flags> {
    return this.flags.update(body);
  }
}
