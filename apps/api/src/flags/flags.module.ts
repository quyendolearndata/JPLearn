import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module";
import { PrismaModule } from "../prisma/prisma.module";
import { FlagsController } from "./flags.controller";
import { FlagsService } from "./flags.service";

@Module({
  imports: [AuthModule, PrismaModule],
  controllers: [FlagsController],
  providers: [FlagsService],
  exports: [FlagsService],
})
export class FlagsModule {}
