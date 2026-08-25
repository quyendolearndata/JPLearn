import { Controller, Get, Inject, Query, Req, UseGuards } from "@nestjs/common";
import { JwtGuard, type AuthenticatedRequest } from "../auth/jwt.guard";
import { CatalogService } from "./catalog.service";

@Controller("catalog")
@UseGuards(JwtGuard)
export class CatalogController {
  constructor(@Inject(CatalogService) private readonly catalog: CatalogService) {}

  @Get()
  list(
    @Query("ci_level") ciLevel: string | undefined,
    @Req() _request: AuthenticatedRequest,
  ) {
    const parsed = ciLevel === undefined ? undefined : Number(ciLevel);
    return this.catalog.listPublished(
      parsed !== undefined && Number.isInteger(parsed) ? parsed : undefined,
    );
  }
}
