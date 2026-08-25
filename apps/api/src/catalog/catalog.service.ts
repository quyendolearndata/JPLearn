import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
} from "@nestjs/common";
import { PrismaService } from "../prisma/prisma.service";
import { toPublic } from "./to-public";

export interface CreateCatalogInput {
  topic_id: string;
  ci_level: number;
  duration_seconds: number;
  media_type: "video" | "audio";
  visual_support: "high" | "medium" | "low";
  title_internal: string;
}

@Injectable()
export class CatalogService {
  constructor(@Inject(PrismaService) private readonly prisma: PrismaService) {}

  async create(input: CreateCatalogInput, createdById: string) {
    const item = await this.prisma.catalogItem.create({
      data: {
        topicId: input.topic_id,
        ciLevel: input.ci_level,
        durationSeconds: input.duration_seconds,
        mediaType: input.media_type,
        visualSupport: input.visual_support,
        titleInternal: input.title_internal,
        createdById,
      },
      include: { media: true },
    });
    return this.staffItem(item);
  }

  async submitQa(id: string) {
    const item = await this.getItem(id);
    if (item.status !== "draft") {
      throw new BadRequestException("Only draft items can be submitted for QA");
    }
    return this.staffItem(await this.prisma.catalogItem.update({
      where: { id },
      data: { status: "level_qa" },
      include: { media: true },
    }));
  }

  async publish(id: string) {
    const item = await this.getItem(id);
    if (item.status !== "level_qa") {
      throw new BadRequestException("Only level_qa items can be published");
    }
    return this.staffItem(await this.prisma.catalogItem.update({
      where: { id },
      data: { status: "published" },
      include: { media: true },
    }));
  }

  async listPublished(ciLevel?: number) {
    const items = await this.prisma.catalogItem.findMany({
      where: {
        status: "published",
        ...(ciLevel === undefined ? {} : { ciLevel }),
      },
      include: { media: true },
      orderBy: { id: "asc" },
    });
    return { items: items.map(toPublic) };
  }

  private async getItem(id: string) {
    const item = await this.prisma.catalogItem.findUnique({ where: { id } });
    if (!item) throw new NotFoundException("Catalog item not found");
    return item;
  }

  private staffItem(item: {
    id: string;
    topicId: string;
    ciLevel: number;
    durationSeconds: number;
    mediaType: string;
    visualSupport: string;
    hasL1Translation: boolean;
    spokenLanguage: string;
    status: string;
    titleInternal: string;
    createdById: string;
    media: Array<{
      id: string;
      catalogItemId: string;
      storageKey: string;
      playbackUrl: string | null;
      hlsUrl: string | null;
      mime: string;
    }>;
  }) {
    return {
      id: item.id,
      topic_id: item.topicId,
      ci_level: item.ciLevel,
      duration_seconds: item.durationSeconds,
      media_type: item.mediaType,
      visual_support: item.visualSupport,
      has_l1_translation: item.hasL1Translation,
      spoken_language: item.spokenLanguage,
      status: item.status,
      title_internal: item.titleInternal,
      created_by: item.createdById,
      media: item.media.map((asset) => ({
        id: asset.id,
        catalog_item_id: asset.catalogItemId,
        storage_key: asset.storageKey,
        playback_url: asset.playbackUrl,
        hls_url: asset.hlsUrl,
        mime: asset.mime,
      })),
    };
  }
}
