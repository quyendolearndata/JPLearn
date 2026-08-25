import {
  CanActivate,
  ExecutionContext,
  Inject,
  Injectable,
  UnauthorizedException,
} from "@nestjs/common";
import { PrismaService } from "../prisma/prisma.service";
import jwt from "jsonwebtoken";

export interface AuthenticatedRequest {
  user: { id: string; email: string; roles: string[] };
  headers: { authorization?: string };
}

@Injectable()
export class JwtGuard implements CanActivate {
  private readonly secret: string;

  constructor(@Inject(PrismaService) private readonly prisma: PrismaService) {
    const secret = process.env.JWT_SECRET;
    if (!secret) throw new Error("JWT_SECRET must be set");
    this.secret = secret;
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
    const header = request.headers.authorization;
    if (!header?.startsWith("Bearer ")) throw new UnauthorizedException();

    try {
      const payload = jwt.verify(header.slice(7), this.secret);
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
      return true;
    } catch (error) {
      if (error instanceof UnauthorizedException) throw error;
      throw new UnauthorizedException();
    }
  }
}
