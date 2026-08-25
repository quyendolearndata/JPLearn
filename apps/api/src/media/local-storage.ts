import { access, mkdir, writeFile } from "node:fs/promises";
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

  hlsDirFor(assetId: string): string {
    return join(this.root, "hls", assetId);
  }

  hlsPathFor(assetId: string, file: string): string {
    return join(this.hlsDirFor(assetId), file);
  }

  async exists(path: string): Promise<boolean> {
    try {
      await access(path);
      return true;
    } catch {
      return false;
    }
  }
}
