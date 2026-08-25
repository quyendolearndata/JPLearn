import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

export class LocalStorage {
  private readonly root = join(process.cwd(), "storage");

  async put(id: string, buffer: Buffer): Promise<string> {
    await mkdir(this.root, { recursive: true });
    const key = `${id}.bin`;
    await writeFile(join(this.root, key), buffer);
    return key;
  }

  pathFor(key: string): string {
    return join(this.root, key);
  }
}
