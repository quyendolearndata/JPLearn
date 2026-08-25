import { Inject, Injectable, OnModuleInit } from "@nestjs/common";
import { PrismaService } from "../prisma/prisma.service";

export const FLAG_KEYS = [
  "speaking_enabled",
  "l1_subtitles_enabled",
  "grammar_enabled",
  "flashcards_enabled",
] as const;

export type Flags = Record<(typeof FLAG_KEYS)[number], boolean>;

@Injectable()
export class FlagsService implements OnModuleInit {
  constructor(@Inject(PrismaService) private readonly prisma: PrismaService) {}

  onModuleInit(): void {
    void this.ensureDefaults().catch(() => undefined);
  }

  async ensureDefaults(): Promise<void> {
    await this.prisma.$transaction(
      FLAG_KEYS.map((key) =>
        this.prisma.featureFlag.upsert({
          where: { key },
          create: { key, value: false },
          update: {},
        }),
      ),
    );
  }

  async get(): Promise<Flags> {
    await this.ensureDefaults();
    const rows = await this.prisma.featureFlag.findMany({
      where: { key: { in: [...FLAG_KEYS] } },
    });
    const values = Object.fromEntries(rows.map(({ key, value }) => [key, value]));
    return Object.fromEntries(
      FLAG_KEYS.map((key) => [key, values[key] ?? false]),
    ) as Flags;
  }

  async update(flags: Flags): Promise<Flags> {
    await this.prisma.$transaction(
      FLAG_KEYS.map((key) =>
        this.prisma.featureFlag.upsert({
          where: { key },
          create: { key, value: flags[key] },
          update: { value: flags[key] },
        }),
      ),
    );
    return this.get();
  }
}
