import {
  BadRequestException,
  Controller,
  Get,
  NotFoundException,
  Param,
  Res,
  StreamableFile,
  UseGuards,
} from "@nestjs/common";
import { createReadStream } from "node:fs";
import { extname } from "node:path";
import { JwtGuard } from "../auth/jwt.guard";
import { MediaService } from "./media.service";
import { LocalStorage } from "./local-storage";

const HLS_CONTENT_TYPES: Record<string, string> = {
  ".m3u8": "application/vnd.apple.mpegurl",
  ".ts": "video/mp2t",
  ".m4s": "video/iso.segment",
  ".mp4": "video/mp4",
  ".vtt": "text/vtt",
};

@Controller("media")
@UseGuards(JwtGuard)
export class MediaStaticController {
  constructor(
    private readonly media: MediaService,
    private readonly storage: LocalStorage,
  ) {}

  @Get(":id")
  async stream(@Param("id") id: string, @Res({ passthrough: true }) response: { type(value: string): void }) {
    const asset = await this.media.get(id);
    response.type(asset.mime);
    return new StreamableFile(createReadStream(this.storage.pathFor(asset.storageKey)));
  }

  // NFR-PERF-002: manifest + segments of an HLS bundle; MP4 route above stays the fallback
  @Get(":id/hls/:file")
  async streamHls(
    @Param("id") id: string,
    @Param("file") file: string,
    @Res({ passthrough: true }) response: { type(value: string): void },
  ) {
    if (!/^[A-Za-z0-9._-]+$/.test(file) || file.includes("..")) {
      throw new BadRequestException("Invalid HLS file name");
    }
    const contentType = HLS_CONTENT_TYPES[extname(file).toLowerCase()];
    if (!contentType) throw new BadRequestException("Unsupported HLS file type");

    await this.media.get(id);
    const path = this.storage.hlsPathFor(id, file);
    if (!(await this.storage.exists(path))) throw new NotFoundException("HLS file not found");

    response.type(contentType);
    return new StreamableFile(createReadStream(path));
  }
}
