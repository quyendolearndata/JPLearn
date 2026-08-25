import {
  Controller,
  Get,
  Param,
  Res,
  StreamableFile,
  UseGuards,
} from "@nestjs/common";
import { createReadStream } from "node:fs";
import { JwtGuard } from "../auth/jwt.guard";
import { MediaService } from "./media.service";
import { LocalStorage } from "./local-storage";

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
}
