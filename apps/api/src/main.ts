import "reflect-metadata";
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors({
    origin: [
      /^http:\/\/localhost:3000$/,
      /^http:\/\/127\.0\.0\.1:3000$/,
      /^exp:\/\//,
    ],
  });
  await app.listen(process.env.PORT ?? 3001);
}

void bootstrap();
