import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module";
import { PrismaModule } from "../prisma/prisma.module";
import { EventsService } from "../events/events.service";
import { ProgressController } from "../progress/progress.controller";
import { SessionsController } from "./sessions.controller";
import { SessionsService } from "./sessions.service";

@Module({
  imports: [PrismaModule, AuthModule],
  controllers: [SessionsController, ProgressController],
  providers: [EventsService, SessionsService],
})
export class SessionsModule {}
