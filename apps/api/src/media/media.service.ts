import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
} from "@nestjs/common";
import { randomUUID } from "node:crypto";
import { PrismaService } from "../prisma/prisma.service";
import { LocalStorage } from "./local-storage";

export const HLS_MANIFEST = "index.m3u8";

@Injectable()
export class MediaService {
  constructor(
    @Inject(PrismaService) private readonly prisma: PrismaService,
    @Inject(LocalStorage) private readonly storage: LocalStorage,
  ) {}

  async upload(catalogItemId: string, file: { buffer: Buffer; mimetype: string }) {
    const item = await this.prisma.catalogItem.findUnique({ where: { id: catalogItemId } });
    if (!item) throw new NotFoundException("Catalog item not found");

    const id = randomUUID();
    const storageKey = await this.storage.put(id, file.buffer);
    const asset = await this.prisma.mediaAsset.create({
      data: {
        id,
        catalogItemId,
        storageKey,
        playbackUrl: `${this.baseUrl()}/media/${id}`,
        mime: file.mimetype,
      },
    });
    return this.toResponse(asset);
  }

  async get(id: string) {
    const asset = await this.prisma.mediaAsset.findUnique({ where: { id } });
    if (!asset) throw new NotFoundException("Media asset not found");
    return asset;
  }

  // NFR-PERF-002: staff registers an HLS bundle already on disk (scripts/transcode-hls.sh)
  async registerHls(id: string) {
    const asset = await this.get(id);
    if (!(await this.storage.exists(this.storage.hlsPathFor(id, HLS_MANIFEST)))) {
      throw new BadRequestException(
        "HLS manifest missing on disk; run scripts/transcode-hls.sh for this asset first",
      );
    }
    const updated = await this.prisma.mediaAsset.update({
      where: { id: asset.id },
      data: { hlsUrl: `${this.baseUrl()}/media/${asset.id}/hls/${HLS_MANIFEST}` },
    });
    return this.toResponse(updated);
  }

  private baseUrl(): string {
    const baseUrl = process.env.API_PUBLIC_URL;
    if (!baseUrl) throw new Error("API_PUBLIC_URL must be set");
    return baseUrl.replace(/\/$/, "");
  }

  private toResponse(asset: {
    id: string;
    catalogItemId: string;
    storageKey: string;
    playbackUrl: string | null;
    hlsUrl: string | null;
    mime: string;
  }) {
    return {
      id: asset.id,
      catalog_item_id: asset.catalogItemId,
      storage_key: asset.storageKey,
      playback_url: asset.playbackUrl,
      hls_url: asset.hlsUrl,
      mime: asset.mime,
    };
  }
}
