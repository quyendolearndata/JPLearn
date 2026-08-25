import { PrismaClient } from "@prisma/client";
import argon2 from "argon2";

const prisma = new PrismaClient();
const keys = [
  "speaking_enabled",
  "l1_subtitles_enabled",
  "grammar_enabled",
  "flashcards_enabled",
];

async function main() {
  await prisma.$transaction(
    keys.map((key) =>
      prisma.featureFlag.upsert({
        where: { key },
        create: { key, value: false },
        update: {},
      }),
    ),
  );
  await prisma.topic.createMany({
    data: [
      "daily_home",
      "food",
      "body",
      "go_somewhere",
      "nature",
      "people",
    ].map((id) => ({ id, labelInternal: id })),
    skipDuplicates: true,
  });

  const admin = await prisma.user.upsert({
    where: { email: "admin@jplearn.local" },
    create: {
      email: "admin@jplearn.local",
      passwordHash: await argon2.hash("password10"),
      roles: { create: [{ role: "admin" }, { role: "teacher" }] },
    },
    update: { passwordHash: await argon2.hash("password10") },
  });
  await prisma.userRole.upsert({
    where: { userId_role: { userId: admin.id, role: "admin" } },
    create: { userId: admin.id, role: "admin" },
    update: {},
  });
  await prisma.userRole.upsert({
    where: { userId_role: { userId: admin.id, role: "teacher" } },
    create: { userId: admin.id, role: "teacher" },
    update: {},
  });

  await prisma.catalogItem.upsert({
    where: { id: "00000000-0000-4000-8000-0000000000c1" },
    create: {
      id: "00000000-0000-4000-8000-0000000000c1",
      topicId: "daily_home",
      ciLevel: 0,
      durationSeconds: 30,
      mediaType: "video",
      visualSupport: "high",
      status: "published",
      titleInternal: "seed-ci0-daily-home",
      createdById: admin.id,
    },
    update: { status: "published" },
  });
  await prisma.catalogItem.upsert({
    where: { id: "00000000-0000-4000-8000-0000000000d1" },
    create: {
      id: "00000000-0000-4000-8000-0000000000d1",
      topicId: "food",
      ciLevel: 1,
      durationSeconds: 25,
      mediaType: "video",
      visualSupport: "high",
      status: "draft",
      titleInternal: "seed-draft-food",
      createdById: admin.id,
    },
    update: { status: "draft" },
  });
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
