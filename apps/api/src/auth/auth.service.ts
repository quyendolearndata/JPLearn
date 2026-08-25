import {
  BadRequestException,
  ConflictException,
  Injectable,
  UnauthorizedException,
} from "@nestjs/common";
import argon2 from "argon2";
import jwt from "jsonwebtoken";
import { randomUUID } from "node:crypto";
import type { AuthSession, UserPublic } from "@jplearn/domain";
import { PrismaService } from "../prisma/prisma.service";
import type { AuthCredentials } from "./dto";

@Injectable()
export class AuthService {
  private readonly secret: string;

  constructor(private readonly prisma: PrismaService) {
    const secret = process.env.JWT_SECRET;
    if (!secret) throw new Error("JWT_SECRET must be set");
    this.secret = secret;
  }

  async hashPassword(plain: string): Promise<string> {
    return argon2.hash(plain);
  }

  async register({ email, password }: AuthCredentials): Promise<AuthSession> {
    if (typeof password !== "string" || password.length < 10) {
      throw new BadRequestException("Password must be at least 10 characters");
    }
    const normalizedEmail = typeof email === "string" ? email.trim().toLowerCase() : "";
    if (!normalizedEmail) throw new BadRequestException("Email is required");
    const passwordHash = await this.hashPassword(password);
    try {
      const user = await this.prisma.user.create({
        data: {
          email: normalizedEmail,
          passwordHash,
          roles: { create: { role: "learner" } },
          progress: { create: { minutesComprehensible: 0, currentCiLevel: 0 } },
        },
        include: { roles: true },
      });
      return this.session(user);
    } catch (error) {
      if ((error as { code?: string }).code === "P2002") {
        throw new ConflictException("Email already registered");
      }
      throw error;
    }
  }

  async login({ email, password }: AuthCredentials): Promise<AuthSession> {
    if (typeof email !== "string" || typeof password !== "string") {
      throw new UnauthorizedException();
    }
    const user = await this.prisma.user.findUnique({
      where: { email: email.trim().toLowerCase() },
      include: { roles: true },
    });
    if (!user || !(await argon2.verify(user.passwordHash, password))) {
      throw new UnauthorizedException();
    }
    return this.session(user);
  }

  async logout(userId: string): Promise<void> {
    await this.prisma.user.update({
      where: { id: userId },
      data: { tokenVersion: { increment: 1 } },
    });
  }

  publicUser(user: { id: string; email: string; roles: Array<{ role: string }> }): UserPublic {
    return { id: user.id, email: user.email, roles: user.roles.map(({ role }) => role as UserPublic["roles"][number]) };
  }

  private session(user: { id: string; email: string; tokenVersion: number; roles: Array<{ role: string }> }): AuthSession {
    const access_token = jwt.sign(
      { sub: user.id, email: user.email, ver: user.tokenVersion },
      this.secret,
      { expiresIn: "8h", jwtid: randomUUID() },
    );
    return { access_token, user: this.publicUser(user) };
  }
}
