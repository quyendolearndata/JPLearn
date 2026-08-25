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
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
