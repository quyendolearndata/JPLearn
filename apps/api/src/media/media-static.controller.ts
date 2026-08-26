import {
  BadRequestException,
  Controller,
  Get,
  Header,
  Inject,
  NotFoundException,
  Param,
  Query,
  Res,
  StreamableFile,
  UseGuards,
} from "@nestjs/common";
import { createReadStream } from "node:fs";
import { readFile } from "node:fs/promises";
import { extname } from "node:path";
import { MediaAccessGuard } from "./media-access.guard";
import { MediaService } from "./media.service";
import { LocalStorage } from "./local-storage";

const HLS_CONTENT_TYPES: Record<string, string> = {
  ".m3u8": "application/vnd.apple.mpegurl",
  ".ts": "video/mp2t",
  ".m4s": "video/iso.segment",
  ".mp4": "video/mp4",
  ".vtt": "text/vtt",
};

// NFR-PERF-002: Chrome ORB chặn segment video/mp2t không có nosniff → hls.js fatal, learner rớt MP4.
@Controller("media")
@UseGuards(MediaAccessGuard)
export class MediaStaticController {
  constructor(
    @Inject(MediaService) private readonly media: MediaService,
    @Inject(LocalStorage) private readonly storage: LocalStorage,
  ) {}

  @Get(":id")
  @Header("X-Content-Type-Options", "nosniff")
  async stream(@Param("id") id: string, @Res({ passthrough: true }) response: { type(value: string): void }) {
    const asset = await this.media.get(id);
    response.type(asset.mime);
    return new StreamableFile(createReadStream(this.storage.pathFor(asset.storageKey)));
  }

  // NFR-PERF-002: manifest + segments of an HLS bundle; MP4 route above stays the fallback
  @Get(":id/hls/:file")
  @Header("X-Content-Type-Options", "nosniff")
  async streamHls(
    @Param("id") id: string,
    @Param("file") file: string,
    @Query("exp") exp: string | undefined,
    @Query("sig") sig: string | undefined,
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

    // Player (hls.js, Safari native) resolve segment tương đối nên làm mất ?exp&sig
    // của manifest → segment 401 → Chrome ORB chặn. Khi request đi qua guard bằng
    // signed URL, ghi lại query ký vào từng dòng URI của manifest để segment tự mang chữ ký.
    if (file.endsWith(".m3u8") && exp && sig) {
      const manifest = await readFile(path, "utf8");
      return manifest
        .split("\n")
        .map((line) => {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith("#")) return line;
          return `${trimmed}?exp=${encodeURIComponent(exp)}&sig=${encodeURIComponent(sig)}`;
        })
        .join("\n");
    }

    return new StreamableFile(createReadStream(path));
  }
}
