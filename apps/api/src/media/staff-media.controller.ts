import { Controller, Param, Post, UseGuards } from "@nestjs/common";
import { JwtGuard } from "../auth/jwt.guard";
import { Roles } from "../auth/roles.decorator";
import { RolesGuard } from "../auth/roles.guard";
import { MediaService } from "./media.service";

@Controller("staff/media")
@UseGuards(JwtGuard, RolesGuard)
export class StaffMediaController {
  constructor(private readonly media: MediaService) {}

  // NFR-PERF-002: mark an uploaded asset as HLS-ready after scripts/transcode-hls.sh produced the bundle
  @Post(":id/hls")
  @Roles("teacher", "admin")
  registerHls(@Param("id") id: string) {
    return this.media.registerHls(id);
  }
}
