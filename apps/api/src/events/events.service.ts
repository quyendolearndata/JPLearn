import { Injectable } from "@nestjs/common";
import type { EventType } from "@jplearn/domain";
import { PrismaService } from "../prisma/prisma.service";

@Injectable()
export class EventsService {
  constructor(private readonly prisma: PrismaService) {}

  record(userId: string, type: EventType, payload: object, sessionId?: string) {
    return this.prisma.learningEvent.create({
      data: { userId, type, payload, sessionId },
    });
  }
}
