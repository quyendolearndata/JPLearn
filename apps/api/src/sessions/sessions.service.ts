import {
  BadRequestException,
  ForbiddenException,
  Inject,
  Injectable,
  NotFoundException,
} from "@nestjs/common";
import { minutesFromDuration, type DeviceClass } from "@jplearn/domain";
import { PrismaService } from "../prisma/prisma.service";
import { EventsService } from "../events/events.service";

@Injectable()
export class SessionsService {
  constructor(
    @Inject(PrismaService) private readonly prisma: PrismaService,
    @Inject(EventsService) private readonly events: EventsService,
  ) {}

  async start(userId: string, deviceClass: DeviceClass) {
    const session = await this.prisma.learningSession.create({
      data: {
        userId,
        deviceClass,
        startedAt: new Date(),
      },
    });
    await this.prisma.device.upsert({
      where: { userId_deviceClass: { userId, deviceClass } },
      update: { lastSeenAt: session.startedAt },
      create: { userId, deviceClass, lastSeenAt: session.startedAt },
    });
    const progress = await this.prisma.learnerProgress.findUniqueOrThrow({ where: { userId } });
    await this.events.record(userId, "session_started", {}, session.id);
    await this.events.record(userId, "level_exposed", { ci_level: progress.currentCiLevel }, session.id);
    return this.toPublic(session);
  }

  async end(userId: string, sessionId: string) {
    const session = await this.prisma.learningSession.findUnique({ where: { id: sessionId } });
    if (!session) throw new NotFoundException("Session not found");
    if (session.userId !== userId) throw new ForbiddenException();
    if (session.endedAt) throw new BadRequestException("Session already ended");

    const endedAt = new Date();
    const duration = Math.floor((endedAt.getTime() - session.startedAt.getTime()) / 1000);
    const minutes = minutesFromDuration(duration);
    await this.prisma.$transaction([
      this.prisma.learningSession.update({
        where: { id: session.id },
        data: { endedAt, durationSeconds: duration },
      }),
      this.prisma.learnerProgress.update({
        where: { userId: session.userId },
        data: { minutesComprehensible: { increment: minutes } },
      }),
    ]);
    await this.events.record(userId, "session_ended", {}, session.id);
    await this.events.record(userId, "minutes_comprehensible", { minutes }, session.id);
    return this.progress(userId);
  }

  progress(userId: string) {
    return this.prisma.learnerProgress.findUniqueOrThrow({
      where: { userId },
      select: { minutesComprehensible: true, currentCiLevel: true },
    }).then(({ minutesComprehensible, currentCiLevel }) => ({
      minutes_comprehensible: minutesComprehensible,
      current_ci_level: currentCiLevel,
    }));
  }

  private toPublic(session: {
    id: string;
    deviceClass: DeviceClass;
    startedAt: Date;
    endedAt: Date | null;
    durationSeconds: number | null;
  }) {
    return {
      id: session.id,
      device_class: session.deviceClass,
      started_at: session.startedAt.toISOString(),
      ended_at: session.endedAt?.toISOString() ?? null,
      duration_seconds: session.durationSeconds,
    };
  }
}
