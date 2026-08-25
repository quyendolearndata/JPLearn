import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module";
import { PrismaModule } from "../prisma/prisma.module";
import { MediaController } from "./media.controller";
import { MediaService } from "./media.service";
import { MediaStaticController } from "./media-static.controller";
import { StaffMediaController } from "./staff-media.controller";
import { LocalStorage } from "./local-storage";

@Module({
  imports: [PrismaModule, AuthModule],
  controllers: [MediaController, MediaStaticController, StaffMediaController],
  providers: [MediaService, LocalStorage],
})
export class MediaModule {}
