# JPLearn Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the JPLearn TypeScript monorepo so one API, web shell, and Expo app (iPhone/iPad/Android) share identity, published catalog, session skeleton, CI-minute progress, CMS publish, and feature flags — with no flashcard, grammar, or L1-translation learner channels.

**Architecture:** pnpm workspace. NestJS API is the only backend; PostgreSQL is source of truth; media files sit on local disk in development (signed/playback URL from API, not a hardcoded CDN). Next.js hosts learner chrome plus `/staff` CMS. Expo uses the same API and `device_class` `phone` | `ipad`. Domain types live in `packages/domain`. Phase 5 CI player and comprehension probes are out of scope.

**Tech Stack:** Node.js 22, pnpm 9, TypeScript 5.7, NestJS 11, Prisma 6, PostgreSQL 16, argon2, `@nestjs/jwt`, Next.js 15 (App Router), Expo SDK 53 + expo-router, Jest + Supertest (API), Playwright (web smoke). Docker Compose for Postgres.

## Global Constraints

- Progress fields are only `minutes_comprehensible` and `current_ci_level` (FR-PRG-003). Do not add `vocabulary_score`, `grammar_lesson_id`, `textbook_percent`, or `translation_pair` as a learner channel.
- Feature flags `speaking_enabled`, `l1_subtitles_enabled`, `grammar_enabled`, `flashcards_enabled` default to `false` (FR-FLG-001). Clients must not render those channels when false (FR-FLG-002).
- Learner catalog items must not include L1 translation fields; `has_l1_translation` is false on published items (FR-CAT-004, FR-NEG-003).
- No HTTP routes or packages named `flashcards`, `grammar`, or learner `translations` (FR-NEG-001, FR-NEG-002, ADR-001).
- Do not create `comprehension_probes` table in migration `0001` (data dictionary).
- Q1 media is MP4 on local/object storage; do not build HLS in this plan (NFR-PERF-002 / ADR-001).
- Do not implement FR-LRN-001..004 (watch CI, picture probe, speaking unlock, recast UI).
- Passwords never stored plaintext; tokens never logged (NFR-SEC-001). HTTPS is required only in staging/prod docs, not localhost.
- Every technical PR/commit message cites SRS ids (for example `FR-ID-001`).
- iPad layout is not a scaled-up phone layout (NFR-XPLAT-002).
- Copy: onboarding/settings Vietnamese; learning chrome has no grammar explanations.
- API contract: `docs/sad/03-design/openapi.yaml`. Spec: `docs/superpowers/specs/2026-08-25-jplearn-foundation-design.md`.

## File map (lock this layout)

```
package.json
pnpm-workspace.yaml
tsconfig.base.json
docker-compose.yml
.github/workflows/ci.yml
packages/domain/src/index.ts
packages/design-tokens/src/index.ts
packages/cms-schema/src/index.ts
apps/api/prisma/schema.prisma
apps/api/prisma/seed.ts
apps/api/src/main.ts
apps/api/src/app.module.ts
apps/api/src/prisma/prisma.service.ts
apps/api/src/request-id.interceptor.ts
apps/api/src/auth/*
apps/api/src/flags/*
apps/api/src/catalog/*
apps/api/src/media/*
apps/api/src/sessions/*
apps/api/src/progress/*
apps/api/src/events/events.service.ts
apps/api/test/*.e2e-spec.ts
apps/web/src/app/login/page.tsx
apps/web/src/app/page.tsx
apps/web/src/app/session/page.tsx
apps/web/src/app/progress/page.tsx
apps/web/src/app/staff/page.tsx
apps/web/src/lib/api.ts
apps/web/src/lib/flags.tsx
apps/mobile/app/login.tsx
apps/mobile/app/(tabs)/catalog.tsx
apps/mobile/app/(tabs)/session.tsx
apps/mobile/app/(tabs)/progress.tsx
apps/mobile/src/deviceClass.ts
apps/mobile/src/api.ts
```

**Types produced by Task 1** (`packages/domain/src/index.ts`) — later tasks must use these names:

```ts
export type Role = "learner" | "teacher" | "admin";
export type DeviceClass = "web" | "phone" | "ipad";
export type CiLevel = 0 | 1 | 2 | 3 | 4;
export type MediaType = "video" | "audio";
export type VisualSupport = "high" | "medium" | "low";
export type CatalogStatus = "draft" | "level_qa" | "published" | "archived";
export type EventType =
  | "session_started"
  | "session_ended"
  | "minutes_comprehensible"
  | "level_exposed";

export interface UserPublic {
  id: string;
  email: string;
  roles: Role[];
}
export interface AuthSession {
  access_token: string;
  user: UserPublic;
}
export interface CatalogItemPublic {
  id: string;
  ci_level: number;
  duration_seconds: number;
  media_type: MediaType;
  topic_id: string;
  visual_support: VisualSupport;
  playback_url?: string;
}
export interface LearnerProgress {
  minutes_comprehensible: number;
  current_ci_level: number;
}
export interface Flags {
  speaking_enabled: boolean;
  l1_subtitles_enabled: boolean;
  grammar_enabled: boolean;
  flashcards_enabled: boolean;
}
export const DEFAULT_FLAGS: Flags = {
  speaking_enabled: false,
  l1_subtitles_enabled: false,
  grammar_enabled: false,
  flashcards_enabled: false,
};
export const ZOMBIE_SESSION_SECONDS = 4 * 60 * 60;
export function minutesFromDuration(durationSeconds: number): number {
  if (durationSeconds > ZOMBIE_SESSION_SECONDS) return 0;
  if (durationSeconds < 0) return 0;
  return Math.floor(durationSeconds / 60);
}
```

---

### Task 1: Monorepo, domain package, forbidden-schema guard

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `tsconfig.base.json`, `.gitignore`, `packages/domain/package.json`, `packages/domain/tsconfig.json`, `packages/domain/src/index.ts`, `packages/domain/src/index.test.ts`, `packages/design-tokens/package.json`, `packages/design-tokens/src/index.ts`, `packages/cms-schema/package.json`, `packages/cms-schema/src/index.ts`, `scripts/assert-no-textbook.ts`

**Interfaces:**
- Consumes: nothing
- Produces: `@jplearn/domain` exports listed in the file map; `pnpm test:guard` fails if forbidden strings appear in `apps/` or `packages/` source

- [ ] **Step 1: Write the failing domain test**

Create `packages/domain/src/index.test.ts`:

```ts
import { DEFAULT_FLAGS, minutesFromDuration, ZOMBIE_SESSION_SECONDS } from "./index";

test("FR-FLG-001 flags default false", () => {
  expect(DEFAULT_FLAGS).toEqual({
    speaking_enabled: false,
    l1_subtitles_enabled: false,
    grammar_enabled: false,
    flashcards_enabled: false,
  });
});

test("FR-PRG-001 minutes floor; zombie adds zero", () => {
  expect(minutesFromDuration(119)).toBe(1);
  expect(minutesFromDuration(ZOMBIE_SESSION_SECONDS + 1)).toBe(0);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/domain && npx tsc --init` is not enough yet. After adding package.json with `"test": "jest"`:

Run: `pnpm --filter @jplearn/domain test`

Expected: FAIL — `Cannot find module './index'` or `minutesFromDuration is not a function`

- [ ] **Step 3: Write workspace + domain implementation**

Root `pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

Root `package.json`:

```json
{
  "name": "jplearn",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "scripts": {
    "test:guard": "tsx scripts/assert-no-textbook.ts",
    "test": "pnpm test:guard && pnpm -r test"
  }
}
```

`packages/domain/src/index.ts`: paste the types block from the file map (including `minutesFromDuration`).

`packages/design-tokens/src/index.ts`:

```ts
export const tokens = {
  colorBg: "#f6f1e8",
  colorText: "#1c1917",
  colorChrome: "#44403c",
  spacePhone: 16,
  spaceIpad: 28,
  fontUi: 'ui-sans-serif, system-ui, "Noto Sans", sans-serif',
} as const;
```

`packages/cms-schema/src/index.ts`:

```ts
export const catalogWriteFields = [
  "topic_id",
  "ci_level",
  "duration_seconds",
  "media_type",
  "visual_support",
  "title_internal",
] as const;
```

`scripts/assert-no-textbook.ts` (FR-NEG-001/002/004):

```ts
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const banned = [
  "vocabulary_score",
  "grammar_lesson_id",
  "textbook_percent",
  "translation_vi",
];
const roots = ["apps", "packages"];

function walk(dir: string, acc: string[] = []): string[] {
  if (!statSync(dir, { throwIfNoEntry: false })) return acc;
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.(ts|tsx|prisma|sql)$/.test(name)) acc.push(p);
  }
  return acc;
}

const hits: string[] = [];
for (const root of roots) {
  for (const file of walk(root)) {
    const text = readFileSync(file, "utf8");
    for (const b of banned) {
      if (text.includes(b)) hits.push(`${file}: ${b}`);
    }
  }
}
if (hits.length) {
  console.error(hits.join("\n"));
  process.exit(1);
}
```

`.gitignore`: `node_modules`, `.next`, `dist`, `.expo`, `apps/api/storage`, `.env`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm install && pnpm --filter @jplearn/domain test && pnpm test:guard`

Expected: PASS (guard passes because `apps/` does not exist yet or has no banned strings)

- [ ] **Step 5: Commit**

```bash
git add package.json pnpm-workspace.yaml tsconfig.base.json .gitignore packages scripts
git commit -m "$(cat <<'EOF'
feat: add monorepo and domain types for CI progress (FR-PRG-001, FR-FLG-001, FR-NEG-004)

EOF
)"
```

---

### Task 2: Postgres, Prisma schema 0001, NestJS bootstrap, request id

**Files:**
- Create: `docker-compose.yml`, `apps/api/package.json`, `apps/api/prisma/schema.prisma`, `apps/api/src/main.ts`, `apps/api/src/app.module.ts`, `apps/api/src/prisma/prisma.module.ts`, `apps/api/src/prisma/prisma.service.ts`, `apps/api/src/request-id.interceptor.ts`, `apps/api/src/health.controller.ts`, `apps/api/test/health.e2e-spec.ts`, `apps/api/test/schema.guard.spec.ts`, `apps/api/.env.example`

**Interfaces:**
- Consumes: domain types (no Prisma models named after banned fields)
- Produces: `PrismaService`; HTTP `GET /health` → `{ ok: true }`; header `x-request-id` on every response (NFR-OBS-001)

- [ ] **Step 1: Write failing schema + health tests**

`apps/api/test/schema.guard.spec.ts`:

```ts
import { readFileSync } from "node:fs";
import { join } from "node:path";

test("FR-NEG-004 prisma has no textbook progress columns", () => {
  const schema = readFileSync(join(__dirname, "../prisma/schema.prisma"), "utf8");
  expect(schema).not.toMatch(/vocabulary_score|grammar_lesson_id|textbook_percent|translation_vi/);
  expect(schema).not.toMatch(/model ComprehensionProbe/);
  expect(schema).toMatch(/minutesComprehensible/);
  expect(schema).toMatch(/currentCiLevel/);
});
```

`apps/api/test/health.e2e-spec.ts`:

```ts
import { INestApplication } from "@nestjs/common";
import { Test } from "@nestjs/testing";
import request from "supertest";
import { AppModule } from "../src/app.module";

describe("health (NFR-OBS-001)", () => {
  let app: INestApplication;
  beforeAll(async () => {
    const m = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = m.createNestApplication();
    await app.init();
  });
  afterAll(() => app.close());

  it("GET /health", async () => {
    const res = await request(app.getHttpServer()).get("/health").expect(200);
    expect(res.body).toEqual({ ok: true });
    expect(res.headers["x-request-id"]).toMatch(/./);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter @jplearn/api test`

Expected: FAIL — missing `schema.prisma` / `AppModule`

- [ ] **Step 3: Write Prisma schema and Nest bootstrap**

`docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: jplearn
      POSTGRES_PASSWORD: jplearn
      POSTGRES_DB: jplearn
    ports: ["5432:5432"]
```

`apps/api/prisma/schema.prisma` — map dictionary names to Prisma camelCase columns via `@map`:

```prisma
generator client {
  provider = "prisma-client-js"
}
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
enum Role { learner teacher admin }
enum DeviceClass { web phone ipad }
enum MediaType { video audio }
enum VisualSupport { high medium low }
enum CatalogStatus { draft level_qa published archived }
enum EventType { session_started session_ended minutes_comprehensible level_exposed }

model User {
  id           String   @id @default(uuid())
  email        String   @unique
  passwordHash String   @map("password_hash")
  createdAt    DateTime @default(now()) @map("created_at")
  roles        UserRole[]
  devices      Device[]
  sessions     LearningSession[]
  progress     LearnerProgress?
  events       LearningEvent[]
  catalogItems CatalogItem[]
  @@map("users")
}
model UserRole {
  userId String @map("user_id")
  role   Role
  user   User   @relation(fields: [userId], references: [id])
  @@id([userId, role])
  @@map("user_roles")
}
model Device {
  id          String      @id @default(uuid())
  userId      String      @map("user_id")
  deviceClass DeviceClass @map("device_class")
  lastSeenAt  DateTime    @map("last_seen_at")
  user        User        @relation(fields: [userId], references: [id])
  @@map("devices")
}
model Topic {
  id             String        @id
  labelInternal  String        @map("label_internal")
  items          CatalogItem[]
  @@map("topics")
}
model CatalogItem {
  id                 String         @id @default(uuid())
  topicId            String         @map("topic_id")
  topic              Topic          @relation(fields: [topicId], references: [id])
  ciLevel            Int            @map("ci_level")
  durationSeconds    Int            @map("duration_seconds")
  mediaType          MediaType      @map("media_type")
  visualSupport      VisualSupport  @map("visual_support")
  hasL1Translation   Boolean        @default(false) @map("has_l1_translation")
  spokenLanguage     String         @default("ja") @map("spoken_language")
  status             CatalogStatus  @default(draft)
  titleInternal      String         @map("title_internal")
  createdById        String         @map("created_by")
  createdBy          User           @relation(fields: [createdById], references: [id])
  media              MediaAsset[]
  @@map("catalog_items")
}
model MediaAsset {
  id            String      @id @default(uuid())
  catalogItemId String      @map("catalog_item_id")
  catalogItem   CatalogItem @relation(fields: [catalogItemId], references: [id])
  storageKey    String      @map("storage_key")
  playbackUrl   String?     @map("playback_url")
  mime          String
  @@map("media_assets")
}
model LearningSession {
  id               String      @id @default(uuid())
  userId           String      @map("user_id")
  user             User        @relation(fields: [userId], references: [id])
  deviceClass      DeviceClass @map("device_class")
  startedAt        DateTime    @map("started_at")
  endedAt          DateTime?   @map("ended_at")
  durationSeconds  Int?        @map("duration_seconds")
  events           LearningEvent[]
  @@map("learning_sessions")
}
model LearnerProgress {
  userId                  String   @id @map("user_id")
  user                    User     @relation(fields: [userId], references: [id])
  minutesComprehensible   Int      @default(0) @map("minutes_comprehensible")
  currentCiLevel          Int      @default(0) @map("current_ci_level")
  updatedAt               DateTime @updatedAt @map("updated_at")
  @@map("learner_progress")
}
model FeatureFlag {
  key   String  @id
  value Boolean
  @@map("feature_flags")
}
model LearningEvent {
  id        String           @id @default(uuid())
  userId    String           @map("user_id")
  user      User             @relation(fields: [userId], references: [id])
  sessionId String?          @map("session_id")
  session   LearningSession? @relation(fields: [sessionId], references: [id])
  type      EventType
  payload   Json
  createdAt DateTime         @default(now()) @map("created_at")
  @@map("learning_events")
}
```

`apps/api/src/request-id.interceptor.ts`:

```ts
import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from "@nestjs/common";
import { randomUUID } from "node:crypto";
import { tap } from "rxjs";

@Injectable()
export class RequestIdInterceptor implements NestInterceptor {
  intercept(ctx: ExecutionContext, next: CallHandler) {
    const res = ctx.switchToHttp().getResponse();
    const req = ctx.switchToHttp().getRequest();
    const id = req.headers["x-request-id"] ?? randomUUID();
    res.setHeader("x-request-id", id);
    return next.handle().pipe(tap(() => undefined));
  }
}
```

`HealthController`: `@Get('/health') health() { return { ok: true }; }`

`main.ts`: `app.useGlobalInterceptors(new RequestIdInterceptor());` CORS enabled for localhost:3000 and Expo. Do not `console.log` authorization headers.

`.env.example`: `DATABASE_URL=postgresql://jplearn:jplearn@localhost:5432/jplearn` `JWT_SECRET=dev-only-change-me` `API_PUBLIC_URL=http://localhost:3001`

- [ ] **Step 4: Run migrate + tests**

Run:

```bash
docker compose up -d db
cd apps/api && cp .env.example .env
pnpm exec prisma migrate dev --name foundation_0001
pnpm test
```

Expected: schema.guard PASS, health e2e PASS, `x-request-id` present

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml apps/api
git commit -m "$(cat <<'EOF'
feat: add API postgres schema and health with request id (NFR-OBS-001, FR-NEG-004)

EOF
)"
```

---

### Task 3: Auth — register, login, logout, me, roles

**Files:**
- Create: `apps/api/src/auth/auth.module.ts`, `apps/api/src/auth/auth.service.ts`, `apps/api/src/auth/auth.controller.ts`, `apps/api/src/auth/jwt.guard.ts`, `apps/api/src/auth/dto.ts`, `apps/api/src/auth/roles.decorator.ts`, `apps/api/src/auth/roles.guard.ts`, `apps/api/test/auth.e2e-spec.ts`, `apps/api/test/helpers.ts`

**Interfaces:**
- Consumes: `PrismaService`; `UserPublic`, `AuthSession`, `Role` from `@jplearn/domain`
- Produces: `POST /auth/register` 201, `POST /auth/login` 200/401, `POST /auth/logout` 204, `GET /me` 200; JWT payload `{ sub: userId, email: string }`; `AuthService.hashPassword(plain: string): Promise<string>` using argon2; register assigns role `learner` only; emails stored lowercase

- [ ] **Step 1: Write failing e2e tests**

`apps/api/test/helpers.ts`:

```ts
import { INestApplication } from "@nestjs/common";
import request from "supertest";

export async function register(
  app: INestApplication,
  email: string,
  password = "password10",
) {
  return request(app.getHttpServer())
    .post("/auth/register")
    .send({ email, password });
}
```

`apps/api/test/auth.e2e-spec.ts`:

```ts
import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { register } from "./helpers";

describe("auth FR-ID-001..004", () => {
  let app: INestApplication;
  let prisma: PrismaService;
  beforeAll(async () => {
    const m = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = m.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);
  });
  afterAll(() => app.close());

  it("registers, logins, me has learner role; password not plaintext", async () => {
    const email = `u${Date.now()}@example.com`;
    const res = await register(app, email).expect(201);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.user.email).toBe(email.toLowerCase());
    expect(res.body.user.roles).toEqual(["learner"]);
    const row = await prisma.user.findUnique({ where: { email: email.toLowerCase() } });
    expect(row?.passwordHash).not.toBe("password10");
    expect(row?.passwordHash).not.toContain("password10");

    await request(app.getHttpServer())
      .post("/auth/login")
      .send({ email, password: "wrong-wrong" })
      .expect(401);

    const me = await request(app.getHttpServer())
      .get("/me")
      .set("Authorization", `Bearer ${res.body.access_token}`)
      .expect(200);
    expect(me.body.roles).toEqual(["learner"]);
    expect(me.body).not.toHaveProperty("passwordHash");
  });

  it("logout then me is 401 FR-ID-003", async () => {
    const email = `l${Date.now()}@example.com`;
    const res = await register(app, email).expect(201);
    await request(app.getHttpServer())
      .post("/auth/logout")
      .set("Authorization", `Bearer ${res.body.access_token}`)
      .expect(204);
    await request(app.getHttpServer())
      .get("/me")
      .set("Authorization", `Bearer ${res.body.access_token}`)
      .expect(401);
  });
});
```

Logout v1: persist denylist table `JwtDeny { jti String @id, exp DateTime }` OR rotate by storing `tokenVersion` on User. **Use `tokenVersion Int @default(0)` on User.** JWT includes `ver`. Logout increments `tokenVersion`. Guard rejects mismatched `ver`. Add `tokenVersion` / `@map("token_version")` in a Prisma migrate `auth_token_version`. This is allowed; it is not a textbook field.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter @jplearn/api test -- auth.e2e-spec`

Expected: FAIL 404 on `/auth/register`

- [ ] **Step 3: Implement AuthService / Controller / JwtGuard / RolesGuard**

`AuthService.register({ email, password })`: if `password.length < 10` throw 400; `email = email.trim().toLowerCase()`; `hash = await argon2.hash(password)`; create user + UserRole learner + LearnerProgress `{ minutesComprehensible: 0, currentCiLevel: 0 }`; return `{ access_token, user }`.

`signToken(user)`: `jwt.sign({ sub: user.id, email: user.email, ver: user.tokenVersion }, JWT_SECRET, { expiresIn: "8h", jwtid: randomUUID() })`.

`login`: find user, `argon2.verify`, 401 if fail.

`logout`: `prisma.user.update({ data: { tokenVersion: { increment: 1 } } })`.

`JwtGuard`: verify signature, load user, if `payload.ver !== user.tokenVersion` throw 401.

Do not log `access_token` or password.

Wire `AuthModule` into `AppModule`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm exec prisma migrate dev --name auth_token_version && pnpm --filter @jplearn/api test -- auth.e2e-spec`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "$(cat <<'EOF'
feat: add email auth, roles, and logout via token version (FR-ID-001, FR-ID-002, FR-ID-003, FR-ID-004, NFR-SEC-001)

EOF
)"
```

---

### Task 4: Feature flags

**Files:**
- Create: `apps/api/src/flags/flags.module.ts`, `apps/api/src/flags/flags.service.ts`, `apps/api/src/flags/flags.controller.ts`, `apps/api/test/flags.e2e-spec.ts`
- Modify: `apps/api/prisma/seed.ts` (create if missing)

**Interfaces:**
- Consumes: `JwtGuard`, `RolesGuard`, `@Roles('admin')`
- Produces: `GET /flags` → `Flags`; `PATCH /staff/flags` admin-only; `FlagsService.ensureDefaults()` inserts four keys false if missing; `FlagsService.get(): Promise<Flags>`

- [ ] **Step 1: Write failing tests**

```ts
it("GET /flags all false FR-FLG-001", async () => {
  const token = (await register(app, `f${Date.now()}@example.com`)).body.access_token;
  const res = await request(app.getHttpServer())
    .get("/flags")
    .set("Authorization", `Bearer ${token}`)
    .expect(200);
  expect(res.body).toEqual({
    speaking_enabled: false,
    l1_subtitles_enabled: false,
    grammar_enabled: false,
    flashcards_enabled: false,
  });
});

it("learner PATCH /staff/flags 403 NFR-SEC-002", async () => {
  const token = (await register(app, `p${Date.now()}@example.com`)).body.access_token;
  await request(app.getHttpServer())
    .patch("/staff/flags")
    .set("Authorization", `Bearer ${token}`)
    .send({ speaking_enabled: true, l1_subtitles_enabled: false, grammar_enabled: false, flashcards_enabled: false })
    .expect(403);
});
```

- [ ] **Step 2: Run tests — expect FAIL 404**

- [ ] **Step 3: Implement FlagsService**

On module init, upsert four keys to `false`. GET maps keys to `Flags`. PATCH requires admin, writes all four booleans. Learner GET is allowed (so clients can hide UI).

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit** `feat: add feature flags default off (FR-FLG-001, NFR-SEC-002)`

---

### Task 5: Catalog CMS + public list

**Files:**
- Create: `apps/api/src/catalog/catalog.module.ts`, `apps/api/src/catalog/catalog.service.ts`, `apps/api/src/catalog/catalog.controller.ts`, `apps/api/src/catalog/staff-catalog.controller.ts`, `apps/api/src/catalog/to-public.ts`, `apps/api/test/catalog.e2e-spec.ts`
- Modify: `apps/api/prisma/seed.ts` — topics `daily_home`, `food`, `body`, `go_somewhere`, `nature`, `people`; admin user `admin@jplearn.local` / `password10` with roles admin+teacher

**Interfaces:**
- Consumes: `Flags` unused here; `CatalogItemPublic` from domain
- Produces: `toPublic(item): CatalogItemPublic` — **must omit** `titleInternal`, `hasL1Translation`, `spokenLanguage`, `status`, `createdBy`; `POST /staff/catalog` teacher|admin → 201 `status=draft`, `has_l1_translation=false`; `POST /staff/catalog/:id/submit-qa` draft→`level_qa`; `POST /staff/catalog/:id/publish` **admin only**, only from `level_qa` → `published`; `GET /catalog?ci_level=` learner sees only `published`

Helper `async function loginAdmin(app)` in `helpers.ts`: seed must run in `beforeAll` via `prisma` upsert admin.

- [ ] **Step 1: Write failing e2e**

```ts
it("draft hidden from learner; published visible; no L1 fields FR-CAT-002 FR-CAT-004", async () => {
  const learnerTok = (await register(app, `c${Date.now()}@example.com`)).body.access_token;
  const adminTok = await adminToken(app);
  const created = await request(app.getHttpServer())
    .post("/staff/catalog")
    .set("Authorization", `Bearer ${adminTok}`)
    .send({
      topic_id: "daily_home",
      ci_level: 0,
      duration_seconds: 30,
      media_type: "video",
      visual_support: "high",
      title_internal: "pour water",
    })
    .expect(201);
  expect(created.body.has_l1_translation).toBe(false);
  expect(created.body.status).toBe("draft");

  const hidden = await request(app.getHttpServer())
    .get("/catalog")
    .set("Authorization", `Bearer ${learnerTok}`)
    .expect(200);
  expect(hidden.body.items.find((i: { id: string }) => i.id === created.body.id)).toBeUndefined();

  await request(app.getHttpServer())
    .post(`/staff/catalog/${created.body.id}/submit-qa`)
    .set("Authorization", `Bearer ${adminTok}`)
    .expect(200);
  await request(app.getHttpServer())
    .post(`/staff/catalog/${created.body.id}/publish`)
    .set("Authorization", `Bearer ${adminTok}`)
    .expect(200);

  const shown = await request(app.getHttpServer())
    .get("/catalog?ci_level=0")
    .set("Authorization", `Bearer ${learnerTok}`)
    .expect(200);
  const item = shown.body.items.find((i: { id: string }) => i.id === created.body.id);
  expect(item).toBeTruthy();
  expect(item).not.toHaveProperty("title_internal");
  expect(item).not.toHaveProperty("has_l1_translation");
  expect(item).not.toHaveProperty("translation_vi");
});

it("learner cannot create catalog NFR-SEC-002", async () => {
  const tok = (await register(app, `n${Date.now()}@example.com`)).body.access_token;
  await request(app.getHttpServer())
    .post("/staff/catalog")
    .set("Authorization", `Bearer ${tok}`)
    .send({
      topic_id: "food",
      ci_level: 0,
      duration_seconds: 10,
      media_type: "video",
      visual_support: "high",
      title_internal: "x",
    })
    .expect(403);
});

it("cannot publish from draft (skip QA)", async () => {
  const adminTok = await adminToken(app);
  const created = await request(app.getHttpServer())
    .post("/staff/catalog")
    .set("Authorization", `Bearer ${adminTok}`)
    .send({
      topic_id: "food",
      ci_level: 1,
      duration_seconds: 10,
      media_type: "audio",
      visual_support: "high",
      title_internal: "skip",
    })
    .expect(201);
  await request(app.getHttpServer())
    .post(`/staff/catalog/${created.body.id}/publish`)
    .set("Authorization", `Bearer ${adminTok}`)
    .expect(400);
});
```

`toPublic` implementation:

```ts
export function toPublic(item: {
  id: string;
  ciLevel: number;
  durationSeconds: number;
  mediaType: "video" | "audio";
  topicId: string;
  visualSupport: "high" | "medium" | "low";
  media: { playbackUrl: string | null }[];
}): CatalogItemPublic {
  return {
    id: item.id,
    ci_level: item.ciLevel,
    duration_seconds: item.durationSeconds,
    media_type: item.mediaType,
    topic_id: item.topicId,
    visual_support: item.visualSupport,
    playback_url: item.media[0]?.playbackUrl ?? undefined,
  };
}
```

JSON keys in HTTP bodies are snake_case matching OpenAPI (`ci_level`, not `ciLevel`).

- [ ] **Step 2: Run — expect FAIL 404**

- [ ] **Step 3: Implement controllers + seed topics + admin**

Publish: if `status !== level_qa` throw `BadRequestException`. Teacher role may POST create and submit-qa; only admin publish (`@Roles('admin')`).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** `feat: add catalog CMS workflow and published-only learner list (FR-CAT-001..005, NFR-SEC-002)`

---

### Task 6: Media upload and playback URL

**Files:**
- Create: `apps/api/src/media/media.module.ts`, `apps/api/src/media/media.controller.ts`, `apps/api/src/media/media.service.ts`, `apps/api/src/media/local-storage.ts`, `apps/api/src/media/media-static.controller.ts`, `apps/api/test/media.e2e-spec.ts`

**Interfaces:**
- Consumes: `CatalogService` item id; env `API_PUBLIC_URL`
- Produces: `POST /staff/catalog/:id/media` multipart field `file`; writes `apps/api/storage/{assetId}.bin`; sets `playbackUrl` to `{API_PUBLIC_URL}/media/{assetId}` (FR-CMS-001, FR-CMS-003, FR-CMS-004); `GET /media/:id` streams file (auth optional for local v1 **or** require JWT — **require JWT** so URLs are not a public CDN guess; learner GET `/catalog` still returns the URL and the player in P5 will send the token. For v1 shell, listing the URL is enough.)

Use `FileInterceptor('file')`. Reject empty file 400. mime from `file.mimetype`.

- [ ] **Step 1: Write failing test** — teacher/admin uploads tiny buffer; GET catalog after publish includes `playback_url` starting with `http://`; learner POST media 403

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement LocalStorage.put(id, buffer)** and staff route

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** `feat: add local media upload and API playback URLs (FR-CMS-001, FR-CMS-003, FR-CMS-004)`

---

### Task 7: Sessions, progress, events

**Files:**
- Create: `apps/api/src/events/events.service.ts`, `apps/api/src/sessions/sessions.module.ts`, `apps/api/src/sessions/sessions.controller.ts`, `apps/api/src/sessions/sessions.service.ts`, `apps/api/src/progress/progress.controller.ts`, `apps/api/test/sessions.e2e-spec.ts`

**Interfaces:**
- Consumes: `minutesFromDuration`, `DeviceClass`, `LearnerProgress` from `@jplearn/domain`; `EventsService.record(userId, type, payload, sessionId?)`
- Produces: `POST /sessions` body `{ device_class }` → 201 `{ id, device_class, started_at, ended_at: null, duration_seconds: null }` and events `session_started` + `level_exposed` with `{ ci_level: progress.currentCiLevel }` (FR-SES-001, FR-SES-003, FR-EVT-001, FR-EVT-003); `POST /sessions/:id/end` sets `ended_at`, `duration_seconds`, adds minutes unless zombie, events `session_ended` and `minutes_comprehensible` `{ minutes }` (FR-SES-002, FR-PRG-001, FR-EVT-002); `GET /progress` `{ minutes_comprehensible, current_ci_level }` **only those two keys** (FR-PRG-002, FR-PRG-003); ending someone else's session 403; double-end 400

- [ ] **Step 1: Write failing tests**

```ts
it("session without media FR-SES-003; progress minutes; no extra keys FR-PRG-003", async () => {
  const tok = (await register(app, `s${Date.now()}@example.com`)).body.access_token;
  const started = await request(app.getHttpServer())
    .post("/sessions")
    .set("Authorization", `Bearer ${tok}`)
    .send({ device_class: "web" })
    .expect(201);
  expect(started.body.device_class).toBe("web");

  await new Promise((r) => setTimeout(r, 1100));
  const ended = await request(app.getHttpServer())
    .post(`/sessions/${started.body.id}/end`)
    .set("Authorization", `Bearer ${tok}`)
    .expect(200);
  expect(Object.keys(ended.body).sort()).toEqual([
    "current_ci_level",
    "minutes_comprehensible",
  ]);
  expect(ended.body.current_ci_level).toBe(0);

  const events = await prisma.learningEvent.findMany({
    where: { sessionId: started.body.id },
  });
  const types = events.map((e) => e.type).sort();
  expect(types).toEqual(
    expect.arrayContaining([
      "session_started",
      "session_ended",
      "level_exposed",
      "minutes_comprehensible",
    ]),
  );
});

it("zombie session adds zero minutes", async () => {
  const tok = (await register(app, `z${Date.now()}@example.com`)).body.access_token;
  const started = await request(app.getHttpServer())
    .post("/sessions")
    .set("Authorization", `Bearer ${tok}`)
    .send({ device_class: "ipad" })
    .expect(201);
  await prisma.learningSession.update({
    where: { id: started.body.id },
    data: { startedAt: new Date(Date.now() - (4 * 60 * 60 + 10) * 1000) },
  });
  const ended = await request(app.getHttpServer())
    .post(`/sessions/${started.body.id}/end`)
    .set("Authorization", `Bearer ${tok}`)
    .expect(200);
  expect(ended.body.minutes_comprehensible).toBe(0);
});
```

For the first test, 1.1s wall clock yields `minutesFromDuration(1) === 0`. That is correct. Assert `minutes_comprehensible >= 0` and events exist; do not assert minutes === 1. Optionally set `startedAt` back 120 seconds via prisma before end to assert `minutes_comprehensible === 2`.

Use the 120-second backdate in the first test so FR-PRG-001 is actually proven.

- [ ] **Step 2: Run — expect FAIL 404**

- [ ] **Step 3: Implement SessionsService.end**

```ts
const duration = Math.floor((endedAt.getTime() - session.startedAt.getTime()) / 1000);
const add = minutesFromDuration(duration);
await prisma.$transaction([
  prisma.learningSession.update({
    where: { id: session.id },
    data: { endedAt, durationSeconds: duration },
  }),
  prisma.learnerProgress.update({
    where: { userId: session.userId },
    data: { minutesComprehensible: { increment: add } },
  }),
]);
```

Upsert Device `lastSeenAt` on start. Payload JSON must never include password.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** `feat: add session skeleton, CI minutes, and learning events (FR-SES-001..003, FR-PRG-001..004, FR-EVT-001..003)`

---

### Task 8: Negative API surface (textbook absent)

**Files:**
- Create: `apps/api/test/neg.e2e-spec.ts`
- Modify: `scripts/assert-no-textbook.ts` if needed to scan `apps/api/src`

**Interfaces:**
- Consumes: running `AppModule` router
- Produces: tests T-NEG-001..004

- [ ] **Step 1: Write failing tests** (they fail only if routes accidentally exist — write tests first, they should **pass** if Tasks 3–7 were clean; if you add a mistaken route they fail)

```ts
const paths = [
  "/flashcards",
  "/grammar",
  "/grammar/lessons",
  "/vocabulary",
  "/translations",
];
it.each(paths)("FR-NEG no %s", async (p) => {
  const tok = (await register(app, `neg${Date.now()}@example.com`)).body.access_token;
  const res = await request(app.getHttpServer())
    .get(p)
    .set("Authorization", `Bearer ${tok}`);
  expect(res.status).toBe(404);
});

it("progress JSON keys only FR-PRG-003", async () => {
  const tok = (await register(app, `keys${Date.now()}@example.com`)).body.access_token;
  const res = await request(app.getHttpServer())
    .get("/progress")
    .set("Authorization", `Bearer ${tok}`)
    .expect(200);
  expect(Object.keys(res.body).sort()).toEqual([
    "current_ci_level",
    "minutes_comprehensible",
  ]);
});
```

- [ ] **Step 2: Run** `pnpm --filter @jplearn/api test -- neg.e2e-spec`

Expected: PASS (404s)

- [ ] **Step 3: If any path hits a wildcard, do not add a controller; Nest default 404 is the implementation**

- [ ] **Step 4: Re-run `pnpm test:guard`**

Expected: PASS

- [ ] **Step 5: Commit** `test: lock absence of textbook channels (FR-NEG-001, FR-NEG-002, FR-NEG-003, FR-NEG-004)`

---

### Task 9: Next.js web shell + staff CMS

**Files:**
- Create: `apps/web/package.json`, `apps/web/next.config.ts`, `apps/web/src/lib/api.ts`, `apps/web/src/lib/auth-storage.ts`, `apps/web/src/lib/flags.tsx`, `apps/web/src/app/layout.tsx`, `apps/web/src/app/login/page.tsx`, `apps/web/src/app/page.tsx`, `apps/web/src/app/session/page.tsx`, `apps/web/src/app/progress/page.tsx`, `apps/web/src/app/staff/page.tsx`, `apps/web/src/app/globals.css`, `apps/web/playwright.config.ts`, `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- Consumes: API at `process.env.NEXT_PUBLIC_API_URL` default `http://localhost:3001`; `Flags`, `CatalogItemPublic`, `LearnerProgress`
- Produces: screens S-LOGIN, S-HOME, S-SESSION, S-PROGRESS, staff CMS; `FlagsProvider` hides any control whose flag is false (do not ship Speak/Flashcard/Grammar buttons at all); staff form fields match `catalogWriteFields`; no translation input

`apps/web/src/lib/api.ts`:

```ts
const base = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001";

export async function api(path: string, opts: RequestInit & { token?: string } = {}) {
  const headers = new Headers(opts.headers);
  headers.set("Content-Type", "application/json");
  if (opts.token) headers.set("Authorization", `Bearer ${opts.token}`);
  const res = await fetch(`${base()}${path}`, { ...opts, headers });
  return res;
}
```

Login page: Vietnamese labels «Email», «Mật khẩu», «Đăng nhập / Đăng ký». Session page: buttons «Bắt đầu phiên» / «Kết thúc phiên» calling `POST /sessions` with `{ device_class: "web" }` then `POST /sessions/{id}/end`. Progress page renders only minutes and level. Home lists catalog grouped by `ci_level`. CSS: `color: #1c1917` on `#f6f1e8` (WCAG AA for chrome, NFR-A11Y-001). Do not add XP badges.

Playwright `e2e/shell.spec.ts` (API + web must be running — document `pnpm --filter @jplearn/api start` and `pnpm --filter @jplearn/web dev`):

```ts
import { test, expect } from "@playwright/test";

test("login and progress have no grammar chrome FR-FLG-002 FR-NEG-002", async ({ page }) => {
  await page.goto("/login");
  const email = `w${Date.now()}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByText("Ngữ pháp")).toHaveCount(0);
  await expect(page.getByText("Flashcard")).toHaveCount(0);
  await page.goto("/progress");
  await expect(page.getByText(/phút/i)).toBeVisible();
});
```

Staff page: only if `roles` includes `teacher` or `admin`; otherwise 403 message. Form: topic select, ci_level, duration, media_type, visual_support, title_internal, file upload, buttons Nộp QA and (admin) Publish.

- [ ] **Step 1: Write Playwright spec first** (fails: web app missing)

- [ ] **Step 2: Run** `pnpm --filter @jplearn/web exec playwright test`

Expected: FAIL connection refused or 404

- [ ] **Step 3: Implement pages listed above**

- [ ] **Step 4: Run Playwright against local API+web**

Expected: PASS

- [ ] **Step 5: Commit** `feat: add web learner shell and staff CMS (FR-ID-001, FR-CAT-002, FR-SES-001, FR-PRG-001, FR-FLG-002, NFR-A11Y-001)`

---

### Task 10: Expo mobile shell (phone vs iPad)

**Files:**
- Create: `apps/mobile/package.json`, `apps/mobile/app.json`, `apps/mobile/app/_layout.tsx`, `apps/mobile/app/login.tsx`, `apps/mobile/app/(tabs)/_layout.tsx`, `apps/mobile/app/(tabs)/catalog.tsx`, `apps/mobile/app/(tabs)/session.tsx`, `apps/mobile/app/(tabs)/progress.tsx`, `apps/mobile/src/api.ts`, `apps/mobile/src/deviceClass.ts`, `apps/mobile/src/deviceClass.test.ts`

**Interfaces:**
- Consumes: same API helpers as web (duplicate small `src/api.ts` — do not invent a fourth client); `DeviceClass`
- Produces: `deviceClass()` → `'ipad'` if `Platform.OS === 'ios' && Math.min(width,height) >= 768` else `'phone'` on native, never `'web'`; session start sends that value (NFR-XPLAT-001, NFR-XPLAT-002); iPad catalog uses 2-column grid and `tokens.spaceIpad`; phone uses 1-column and `tokens.spacePhone`; tabs Catalog | Phiên | Tiến độ; no Speak tab

- [ ] **Step 1: Write failing unit test**

```ts
import { deviceClassFrom } from "./deviceClass";

test("NFR-XPLAT-002 ipad vs phone", () => {
  expect(deviceClassFrom({ os: "ios", width: 390, height: 844 })).toBe("phone");
  expect(deviceClassFrom({ os: "ios", width: 1024, height: 1366 })).toBe("ipad");
  expect(deviceClassFrom({ os: "android", width: 1024, height: 1366 })).toBe("phone");
});
```

Pure function — Android tablet still reports `phone` in v1 unless you also treat `width>=768` on android as phone-class layout with larger padding; **spec device_class enum is web|phone|ipad**. Android tablet → `phone` (enum has no android_tablet). iPad only when iOS and min dimension ≥ 768.

- [ ] **Step 2: Run** `pnpm --filter @jplearn/mobile test`

Expected: FAIL missing module

- [ ] **Step 3: Implement `deviceClassFrom` and screens**

```ts
export function deviceClassFrom(p: { os: string; width: number; height: number }): "phone" | "ipad" {
  const min = Math.min(p.width, p.height);
  if (p.os === "ios" && min >= 768) return "ipad";
  return "phone";
}
```

Catalog iPad: `numColumns={2}` and padding 28. Phone: `numColumns={1}` padding 16. Same API token storage (`expo-secure-store`).

- [ ] **Step 4: Run unit test PASS. Manual: `pnpm --filter @jplearn/mobile start` — login, start session, confirm progress matches web for same user (FR-PRG-004, T-ID-002).**

- [ ] **Step 5: Commit** `feat: add Expo shell with distinct iPad layout (NFR-XPLAT-001, NFR-XPLAT-002, FR-SES-001)`

---

### Task 11: Seed, runbooks, same-user three-surface check

**Files:**
- Create: `apps/api/prisma/seed.ts` (finalize), `README.md`, `docs/sad/03-design/runbook-publish.md`
- Modify: `package.json` scripts `dev:api`, `dev:web`, `db:seed`

**Interfaces:**
- Consumes: all previous modules
- Produces: seed topics + admin + four flags false; README how to run API `:3001`, web `:3000`, Expo; runbook: publish → wait → GET `/catalog` on three clients ≤ 5 minutes (NFR-PERF-001)

Seed flags and topics idempotent. Seed does not create learner flashcards.

README sections: Prerequisites (Node 22, Docker, pnpm), `docker compose up -d db`, `pnpm install`, `pnpm --filter @jplearn/api exec prisma migrate dev`, `pnpm --filter @jplearn/api exec prisma db seed`, `pnpm --filter @jplearn/api start`, `pnpm --filter @jplearn/web dev`.

`runbook-publish.md`: steps to create item, QA, publish, curl catalog as learner; note MP4 not HLS.

- [ ] **Step 1: Write seed file and a seed test** that `feature_flags` four rows are false after seed

- [ ] **Step 2: Run seed on empty DB — fail if seed missing**

- [ ] **Step 3: Implement seed + README + runbook**

- [ ] **Step 4: Manually log in as same user on web and record minutes; log in Expo and GET progress — numbers match**

- [ ] **Step 5: Commit** `docs: add seed, README, and publish runbook (NFR-PERF-001, FR-PRG-004)`

---

### Task 12: CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Jest API tests, domain tests, guard script, Playwright (web) optional if services started
- Produces: CI job on Ubuntu: start Postgres service, `pnpm install`, `pnpm test:guard`, `pnpm --filter @jplearn/domain test`, `pnpm --filter @jplearn/api test`, Prisma migrate

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: jplearn
          POSTGRES_PASSWORD: jplearn
          POSTGRES_DB: jplearn
        ports: ["5432:5432"]
    env:
      DATABASE_URL: postgresql://jplearn:jplearn@localhost:5432/jplearn
      JWT_SECRET: ci-secret
      API_PUBLIC_URL: http://localhost:3001
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm }
      - run: pnpm install
      - run: pnpm test:guard
      - run: pnpm --filter @jplearn/domain test
      - run: pnpm --filter @jplearn/api exec prisma migrate deploy
      - run: pnpm --filter @jplearn/api test
```

- [ ] **Step 1: Add workflow file**
- [ ] **Step 2: Push is not required in this task; run the same commands locally**
- [ ] **Step 3: Fix any CI-only path issues**
- [ ] **Step 4: Confirm local command sequence matches workflow**
- [ ] **Step 5: Commit** `ci: add postgres-backed API and domain tests (NFR-OBS-001)`

---

## Spec coverage (self-review)

| Req | Task |
|---|---|
| FR-ID-001..004 | 3 |
| FR-CAT-001..005 | 5 |
| FR-SES-001..003 | 7 |
| FR-PRG-001..004 | 7, 10, 11 |
| FR-CMS-001..004 | 5, 6 |
| FR-FLG-001..002 | 4, 9, 10 |
| FR-EVT-001..003 | 7 |
| FR-NEG-001..004 | 1, 2, 8 |
| NFR-XPLAT-001..002 | 10, 11 |
| NFR-PERF-001 | 11 runbook (no HLS) |
| NFR-PERF-002 HLS | out of this plan (ADR Q1 MP4) |
| NFR-SEC-001..002 | 3, 4, 5 |
| NFR-PRIV-001 | 3 (email+id only on UserPublic) |
| NFR-A11Y-001 | 9 contrast; no P5 player keyboard |
| NFR-OBS-001 | 2 |
| FR-LRN-* | not implemented |

Gaps left for later plans: HLS, 15 PNG wireframes, production HTTPS, Playwright in CI, Android tablet `device_class` (stays `phone`).

## Placeholder scan

No TBD. Media is local disk, not “add S3 later” inside a step — S3 is a future ADR. HLS is explicitly out of this plan.
