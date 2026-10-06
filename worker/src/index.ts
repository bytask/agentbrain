/**
 * agentbrain-mcp — agentbrain（仕事の文脈を AI に渡すフォルダ）の作り方・点検の手順と雛形を
 * MCP で配る Cloudflare Worker。プラグインを入れられない環境でも、コネクタを足せば同じ手順が届く。
 *
 *   公開: mcp-gateway 経由 https://mcp.taskf.co.jp/agentbrain/<secret> → /mcp-<MCP_PATH_SECRET>
 *   ツール: agentbrain_guide / agentbrain_template
 *   プロンプト: agentbrain-setup / agentbrain-check、リソース: agentbrain://template/<path>
 *   ステートレス（Durable Object なし、GET の SSE は 405）。ファイルは書かない（書くのはクライアント側）
 *
 * 中身（GUIDES / TEMPLATE）は scripts/build.py が skills/ から生成する content.gen.ts にある。
 */
import { GUIDES, TEMPLATE, VERSION } from "./content.gen";

export interface Env {
  MCP_PATH_SECRET: string;
}

const PROTOCOL = "2025-06-18";
const FENCE = "~~~~";
const URI_PREFIX = "agentbrain://template/";

type Topic = keyof typeof GUIDES;
const TOPICS = Object.keys(GUIDES) as Topic[];

const INSTRUCTIONS = [
  "agentbrain（ある人の仕事を AI が進めるための文脈を置くフォルダ）を作る・続ける・点検するための手順と雛形を配るサーバー。",
  "「agentbrain を作って」「agentbrain の続き」「業務を追加して」と言われたら agentbrain_guide(topic=setup) を、「agentbrain を点検して」と言われたら agentbrain_guide(topic=check) を呼び、返ってきた手順に従う。",
  "雛形のファイルは agentbrain_template が返す。",
  "このサーバーはファイルを読み書きしない。フォルダへの書き込みは、手元のファイル操作で行う。",
].join("\n");

// ---------- tool definitions ----------

const TOOLS = [
  {
    name: "agentbrain_guide",
    description:
      "agentbrain の手順書を返す。setup = 新しく作ってインタビューで埋める・続きから再開する・業務を追加する。check = 既にある agentbrain を点検する（受け皿の片付け、未記入、古い記述、矛盾、決まりへの昇格）。作業を始める前に必ず読む。",
    inputSchema: {
      type: "object",
      properties: {
        topic: { type: "string", enum: TOPICS, description: "setup（作る・続ける・業務を足す）か check（点検する）。省略時は setup" },
      },
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true },
  },
  {
    name: "agentbrain_template",
    description:
      "agentbrain の雛形ファイルを返す。path を省くと全ファイル（相対パスと中身）、path を渡すとその 1 ファイル。返ってきた中身は、変えずにそのまま同じ相対パスへ書き出す。",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "雛形内の相対パス（例: 20-業務/_ひな形/概要.md）。省略時は全ファイル" },
      },
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true },
  },
];

const PROMPTS = [
  { name: "agentbrain-setup", description: "agentbrain を作る・続きから再開する・業務を追加する", topic: "setup" as Topic },
  { name: "agentbrain-check", description: "agentbrain を点検する", topic: "check" as Topic },
];

// ---------- content ----------

const nfc = (s: string) => s.normalize("NFC").replace(/^\.?\/+/, "");

function renderFiles(files: readonly { path: string; content: string }[]): string {
  return files.map((f) => `### \`${f.path}\`\n\n${FENCE}markdown\n${f.content}\n${FENCE}`).join("\n\n");
}

function runTool(name: string, a: Record<string, unknown>): string {
  switch (name) {
    case "agentbrain_guide": {
      const topic = (typeof a.topic === "string" ? a.topic : "setup") as Topic;
      if (!TOPICS.includes(topic)) throw new Error(`topic は ${TOPICS.join(" / ")} のどちらか`);
      return GUIDES[topic];
    }
    case "agentbrain_template": {
      if (typeof a.path !== "string" || !a.path) {
        return `雛形 ${TEMPLATE.length} ファイル。見出しが置き場所からの相対パスで、囲みの中がファイルの中身。\n\n${renderFiles(TEMPLATE)}`;
      }
      const wanted = nfc(a.path);
      const file = TEMPLATE.find((f) => f.path === wanted);
      if (!file) throw new Error(`雛形に無いパス: ${a.path}\n使えるパス:\n${TEMPLATE.map((f) => "- " + f.path).join("\n")}`);
      return renderFiles([file]);
    }
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// ---------- MCP (Streamable HTTP, stateless) ----------

type Req = { jsonrpc: "2.0"; id?: number | string | null; method: string; params?: Record<string, unknown> };
const ok = (id: Req["id"], result: unknown) => ({ jsonrpc: "2.0", id: id ?? null, result });
const err = (id: Req["id"], code: number, message: string) => ({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });

function handleRpc(r: Req): unknown | undefined {
  if (r.method.startsWith("notifications/")) return undefined;
  switch (r.method) {
    case "initialize": {
      const v = (r.params?.protocolVersion as string) || PROTOCOL;
      return ok(r.id, {
        protocolVersion: /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : PROTOCOL,
        capabilities: { tools: { listChanged: false }, prompts: { listChanged: false }, resources: { listChanged: false } },
        serverInfo: { name: "agentbrain-mcp", version: VERSION },
        instructions: INSTRUCTIONS,
      });
    }
    case "ping":
      return ok(r.id, {});
    case "tools/list":
      return ok(r.id, { tools: TOOLS });
    case "tools/call": {
      const name = r.params?.name as string;
      const args = (r.params?.arguments as Record<string, unknown>) ?? {};
      if (!TOOLS.some((t) => t.name === name)) return err(r.id, -32602, `Unknown tool: ${name}`);
      try {
        return ok(r.id, { content: [{ type: "text", text: runTool(name, args) }], isError: false });
      } catch (e) {
        return ok(r.id, { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true });
      }
    }
    case "prompts/list":
      return ok(r.id, { prompts: PROMPTS.map(({ name, description }) => ({ name, description })) });
    case "prompts/get": {
      const prompt = PROMPTS.find((p) => p.name === r.params?.name);
      if (!prompt) return err(r.id, -32602, `Unknown prompt: ${r.params?.name}`);
      return ok(r.id, {
        description: prompt.description,
        messages: [{ role: "user", content: { type: "text", text: GUIDES[prompt.topic] } }],
      });
    }
    case "resources/list":
      return ok(r.id, {
        resources: TEMPLATE.map((f) => ({ uri: URI_PREFIX + encodeURI(f.path), name: f.path, mimeType: "text/markdown" })),
      });
    case "resources/templates/list":
      return ok(r.id, { resourceTemplates: [] });
    case "resources/read": {
      const uri = String(r.params?.uri ?? "");
      const path = uri.startsWith(URI_PREFIX) ? nfc(decodeURI(uri.slice(URI_PREFIX.length))) : "";
      const file = TEMPLATE.find((f) => f.path === path);
      if (!file) return err(r.id, -32002, `Resource not found: ${uri}`);
      return ok(r.id, { contents: [{ uri, mimeType: "text/markdown", text: file.content }] });
    }
    default:
      return err(r.id, -32601, `Method not found: ${r.method}`);
  }
}

async function serveMcp(request: Request): Promise<Response> {
  const headers = { "content-type": "application/json", "cache-control": "no-store" };
  if (request.method === "GET") return new Response(null, { status: 405, headers: { allow: "POST, DELETE" } });
  if (request.method === "DELETE") return new Response(null, { status: 200, headers });
  if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405, headers: { allow: "POST, DELETE" } });
  let parsed: unknown;
  try {
    parsed = await request.json();
  } catch {
    return new Response(JSON.stringify(err(null, -32700, "Parse error")), { status: 400, headers });
  }
  const reqs = (Array.isArray(parsed) ? parsed : [parsed]) as Req[];
  const responses = reqs.map(handleRpc).filter((x) => x !== undefined);
  if (!responses.length) return new Response(null, { status: 202, headers });
  return new Response(JSON.stringify(Array.isArray(parsed) ? responses : responses[0]), { status: 200, headers });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);
    if (pathname === "/" || pathname === "/health") return new Response("agentbrain-mcp ok\n", { headers: { "content-type": "text/plain" } });
    if (env.MCP_PATH_SECRET) {
      const base = `/mcp-${env.MCP_PATH_SECRET}`;
      if (pathname === base || pathname === `${base}/`) return serveMcp(request);
    }
    return new Response("Not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
