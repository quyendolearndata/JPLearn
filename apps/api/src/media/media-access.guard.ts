import { CanActivate, ExecutionContext, Inject, Injectable, UnauthorizedException } from "@nestjs/common";
import jwt from "jsonwebtoken";
import { PrismaService } from "../prisma/prisma.service";
import { verifyMediaSig } from "./signed-url";

@Injectable()
export class MediaAccessGuard implements CanActivate {
  private readonly jwtSecret: string;

  constructor(@Inject(PrismaService) private readonly prisma: PrismaService) {
    const secret = process.env.JWT_SECRET;
    if (!secret) throw new Error("JWT_SECRET must be set");
    this.jwtSecret = secret;
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest<{
      headers: { authorization?: string };
      params: { id?: string };
      query: { exp?: string; sig?: string };
      user?: { id: string; email: string; roles: string[] };
    }>();

    const header = request.headers.authorization;
    if (header?.startsWith("Bearer ")) {
      await this.attachUser(request, header.slice(7));
      return true;
    }

    const assetId = request.params.id;
    const exp = Number(request.query.exp);
    const sig = request.query.sig ?? "";
    if (assetId && verifyMediaSig({ assetId, exp, sig })) return true;

    throw new UnauthorizedException();
  }

  private async attachUser(
    request: { user?: { id: string; email: string; roles: string[] } },
    token: string,
  ) {
    try {
      const payload = jwt.verify(token, this.jwtSecret);
      if (typeof payload === "string" || !payload.sub || typeof payload.ver !== "number") {
        throw new UnauthorizedException();
      }
      const user = await this.prisma.user.findUnique({
        where: { id: payload.sub },
        include: { roles: true },
      });
      if (!user || payload.ver !== user.tokenVersion) throw new UnauthorizedException();
      request.user = {
        id: user.id,
        email: user.email,
        roles: user.roles.map(({ role }) => role),
      };
    } catch (error) {
      if (error instanceof UnauthorizedException) throw error;
      throw new UnauthorizedException();
    }
  }
}
