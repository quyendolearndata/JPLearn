import {
  BadRequestException,
  Controller,
  Inject,
  Param,
  Post,
  UploadedFile,
  UseGuards,
  UseInterceptors,
} from "@nestjs/common";
import { FileInterceptor } from "@nestjs/platform-express";
import { JwtGuard } from "../auth/jwt.guard";
import { Roles } from "../auth/roles.decorator";
import { RolesGuard } from "../auth/roles.guard";
import { MediaService } from "./media.service";

@Controller("staff/catalog")
@UseGuards(JwtGuard, RolesGuard)
export class MediaController {
  constructor(@Inject(MediaService) private readonly media: MediaService) {}

  @Post(":id/media")
  @Roles("teacher", "admin")
  @UseInterceptors(FileInterceptor("file"))
  upload(
    @Param("id") id: string,
    @UploadedFile() file: { buffer: Buffer; mimetype: string; size: number } | undefined,
  ) {
    if (!file || file.size === 0) throw new BadRequestException("File must not be empty");
    return this.media.upload(id, file);
  }
}
