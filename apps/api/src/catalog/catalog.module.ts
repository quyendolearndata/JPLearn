import { Module } from "@nestjs/common";
import { AuthModule } from "../auth/auth.module";
import { PrismaModule } from "../prisma/prisma.module";
import { CatalogController } from "./catalog.controller";
import { CatalogService } from "./catalog.service";
import { StaffCatalogController } from "./staff-catalog.controller";

@Module({
  imports: [PrismaModule, AuthModule],
  controllers: [CatalogController, StaffCatalogController],
  providers: [CatalogService],
  exports: [CatalogService],
})
export class CatalogModule {}
