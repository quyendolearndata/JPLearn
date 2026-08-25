import { Injectable, NotFoundException } from "@nestjs/common";
import { randomUUID } from "node:crypto";
import { PrismaService } from "../prisma/prisma.service";
import { LocalStorage } from "./local-storage";

@Injectable()
export class MediaService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly storage: LocalStorage,
  ) {}

  async upload(catalogItemId: string, file: { buffer: Buffer; mimetype: string }) {
    const item = await this.prisma.catalogItem.findUnique({ where: { id: catalogItemId } });
    if (!item) throw new NotFoundException("Catalog item not found");

    const id = randomUUID();
    const storageKey = await this.storage.put(id, file.buffer);
    const baseUrl = process.env.API_PUBLIC_URL;
    if (!baseUrl) throw new Error("API_PUBLIC_URL must be set");
    const asset = await this.prisma.mediaAsset.create({
      data: {
        id,
        catalogItemId,
        storageKey,
        playbackUrl: `${baseUrl.replace(/\/$/, "")}/media/${id}`,
        mime: file.mimetype,
      },
    });
    return {
      id: asset.id,
      catalog_item_id: asset.catalogItemId,
      storage_key: asset.storageKey,
      playback_url: asset.playbackUrl,
      mime: asset.mime,
    };
  }

  async get(id: string) {
    const asset = await this.prisma.mediaAsset.findUnique({ where: { id } });
    if (!asset) throw new NotFoundException("Media asset not found");
    return asset;
  }
}
