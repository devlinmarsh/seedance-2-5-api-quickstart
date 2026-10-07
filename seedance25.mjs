// Seedance 2.5 API client for Node.js 18+ (built-in fetch, no dependencies).
//
//   export SEEDANCE_API_KEY=...
//   node seedance25.mjs "A slow aerial shot over a foggy pine forest at sunrise"

import { writeFile } from "node:fs/promises";

const DEFAULT_BASE_URL = "https://argolink.io/v1";
const MODEL = "seedance-2.5";

export class SeedanceError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export class Seedance25 {
  constructor({ apiKey = process.env.SEEDANCE_API_KEY, baseUrl = process.env.SEEDANCE_BASE_URL || DEFAULT_BASE_URL } = {}) {
    if (!apiKey) throw new SeedanceError("set SEEDANCE_API_KEY or pass apiKey");
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  async #request(method, path, body) {
    const response = await fetch(this.baseUrl + path, {
      method,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new SeedanceError(`${method} ${path} returned ${response.status}: ${text.slice(0, 300)}`, response.status, text);
    }
    return response;
  }

  /** Start a job and return its request_id. */
  async submit(prompt, fields = {}) {
    const response = await this.#request("POST", "/videos/generations", { model: MODEL, prompt, ...fields });
    return (await response.json()).request_id;
  }

  async status(requestId) {
    return (await this.#request("GET", `/videos/${requestId}`)).json();
  }

  /** Poll until done; throw on failed, expired or after maxWaitMs. */
  async wait(requestId, { intervalMs = 5000, maxWaitMs = 30 * 60 * 1000, onProgress } = {}) {
    const deadline = Date.now() + maxWaitMs;
    for (;;) {
      const job = await this.status(requestId);
      if (job.status === "done") return job;
      if (job.status === "failed" || job.status === "expired") {
        throw new SeedanceError(`job ${requestId} ended as ${job.status}`, undefined, job);
      }
      onProgress?.(job);
      if (Date.now() > deadline) throw new SeedanceError(`job ${requestId} still ${job.status}`, undefined, job);
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  }

  async download(requestId, path = "output.mp4") {
    const response = await this.#request("GET", `/videos/${requestId}/content`);
    await writeFile(path, Buffer.from(await response.arrayBuffer()));
    return path;
  }

  /** submit + wait + download; returns the final job (usage holds the billed seconds). */
  async generate(prompt, fields = {}, path = "output.mp4") {
    const requestId = await this.submit(prompt, fields);
    const job = await this.wait(requestId, { onProgress: (j) => console.error(`${j.progress ?? 0}%`) });
    await this.download(requestId, path);
    return job;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const prompt = process.argv[2];
  if (!prompt) {
    console.error('usage: node seedance25.mjs "your prompt" [output.mp4]');
    process.exit(1);
  }
  const job = await new Seedance25().generate(prompt, { duration: 5, resolution: "720p", aspect_ratio: "16:9" }, process.argv[3]);
  console.log(JSON.stringify(job.usage ?? {}));
}
