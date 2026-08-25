import { Module } from "@nestjs/common";
import { APP_INTERCEPTOR } from "@nestjs/core";
import { HealthController } from "./health.controller";
import { PrismaModule } from "./prisma/prisma.module";
import { RequestIdInterceptor } from "./request-id.interceptor";
import { AuthModule } from "./auth/auth.module";
import { FlagsModule } from "./flags/flags.module";
import { CatalogModule } from "./catalog/catalog.module";
import { MediaModule } from "./media/media.module";
import { SessionsModule } from "./sessions/sessions.module";

@Module({
  imports: [PrismaModule, AuthModule, FlagsModule, CatalogModule, MediaModule, SessionsModule],
  controllers: [HealthController],
  providers: [{ provide: APP_INTERCEPTOR, useClass: RequestIdInterceptor }],
})
export class AppModule {}
