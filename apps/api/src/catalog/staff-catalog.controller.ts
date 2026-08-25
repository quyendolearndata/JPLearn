import {
  Body,
  Controller,
  HttpCode,
  Inject,
  Param,
  Post,
  Req,
  UseGuards,
} from "@nestjs/common";
import { JwtGuard, type AuthenticatedRequest } from "../auth/jwt.guard";
import { Roles } from "../auth/roles.decorator";
import { RolesGuard } from "../auth/roles.guard";
import { CatalogService, type CreateCatalogInput } from "./catalog.service";

@Controller("staff/catalog")
@UseGuards(JwtGuard, RolesGuard)
export class StaffCatalogController {
  constructor(@Inject(CatalogService) private readonly catalog: CatalogService) {}

  @Post()
  @Roles("teacher", "admin")
  create(
    @Body() body: CreateCatalogInput,
    @Req() request: AuthenticatedRequest,
  ) {
    return this.catalog.create(body, request.user.id);
  }

  @Post(":id/submit-qa")
  @HttpCode(200)
  @Roles("teacher", "admin")
  submitQa(@Param("id") id: string) {
    return this.catalog.submitQa(id);
  }

  @Post(":id/publish")
  @HttpCode(200)
  @Roles("admin")
  publish(@Param("id") id: string) {
    return this.catalog.publish(id);
  }
}
