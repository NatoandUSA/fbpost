/** Privacy-first Cloudflare Worker + D1 backend. */
const MAX_BODY_BYTES = 225_000;
const MAX_RECORD_BYTES = 200_000;
const DEFAULT_RETENTION_DAYS = 90;

function appOrigin(env) { return String(env.APP_ORIGIN || "").replace(/\/$/, ""); }
function sameOrigin(req, env) { return Boolean(appOrigin(env) && req.headers.get("Origin") === appOrigin(env)); }
function cors(req, env) { return sameOrigin(req, env) ? { "Access-Control-Allow-Origin": appOrigin(env), Vary: "Origin" } : { Vary: "Origin" }; }
function json(body, status, req, env) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin", ...cors(req, env) } });
}
function text(value) { return typeof value === "string" ? value.trim() : ""; }
function bounded(value, max) { return text(value).slice(0, max); }

// Hash both inputs before comparing, so a secret is never compared byte-by-byte directly.
async function secureEqual(left, right) {
  if (typeof left !== "string" || typeof right !== "string" || !left || !right) return false;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([crypto.subtle.digest("SHA-256", enc.encode(left)), crypto.subtle.digest("SHA-256", enc.encode(right))]);
  const aa = new Uint8Array(a), bb = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < aa.length; i++) diff |= aa[i] ^ bb[i];
  return diff === 0;
}
function bearer(req) { const value = req.headers.get("Authorization") || ""; return value.startsWith("Bearer ") ? value.slice(7).trim() : ""; }
function validMaster(req, env) { return secureEqual(bearer(req), env.MASTER_KEY || ""); }
function retentionDays(env) { const n = Number.parseInt(env.RETENTION_DAYS, 10); return Number.isInteger(n) && n >= 7 && n <= 365 ? n : DEFAULT_RETENTION_DAYS; }
async function purgeExpired(env) { const cutoff = new Date(Date.now() - retentionDays(env) * 86_400_000).toISOString(); await env.DB.prepare("DELETE FROM submissions WHERE created_at < ?").bind(cutoff).run(); }

async function verifyTurnstile(token, req, env) {
  if (!env.TURNSTILE_SECRET || !token) return false;
  const form = new FormData();
  form.append("secret", env.TURNSTILE_SECRET); form.append("response", token);
  const ip = req.headers.get("CF-Connecting-IP"); if (ip) form.append("remoteip", ip);
  const response = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
  if (!response.ok) return false;
  const result = await response.json();
  return result && result.success === true;
}
async function limited(path, body, env) {
  if (!env.API_RATE_LIMIT) return false; // fail closed until a limiter is configured
  const key = path === "/api/submit" ? `submit:${text(body.team)}` : `admin:${path}`;
  return (await env.API_RATE_LIMIT.limit({ key })).success;
}
async function parseBody(req) {
  const length = Number(req.headers.get("Content-Length"));
  if (!Number.isFinite(length) || length < 1 || length > MAX_BODY_BYTES) return { error: "Kích thước request không hợp lệ." };
  if (!req.headers.get("Content-Type")?.toLowerCase().startsWith("application/json")) return { error: "Content-Type phải là application/json." };
  try { const body = await req.json(); return body && typeof body === "object" && !Array.isArray(body) ? { body } : { error: "Dữ liệu gửi lên không hợp lệ." }; }
  catch { return { error: "JSON không hợp lệ." }; }
}
function recordFrom(body) {
  if (!body.data || typeof body.data !== "object" || Array.isArray(body.data) || !body.appeal || typeof body.appeal !== "object" || Array.isArray(body.appeal)) return null;
  const data = JSON.stringify(body.data), appeal = JSON.stringify(body.appeal);
  if (data.length + appeal.length > MAX_RECORD_BYTES) return null;
  return { name: bounded(body.name, 120), shop: bounded(body.shop, 120), data, appeal };
}

export default {
  async fetch(req, env, ctx) {
    const path = new URL(req.url).pathname;
    if (!path.startsWith("/api/")) {
      if (!env.ASSETS) return new Response("Not found", { status: 404 });
      const asset = await env.ASSETS.fetch(req);
      const headers = new Headers(asset.headers);
      headers.set("X-Content-Type-Options", "nosniff");
      headers.set("X-Frame-Options", "DENY");
      headers.set("Referrer-Policy", "same-origin");
      headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
      headers.set("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com data:; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
      return new Response(asset.body, { status: asset.status, statusText: asset.statusText, headers });
    }
    if (req.method === "OPTIONS") return sameOrigin(req, env)
      ? new Response(null, { headers: { ...cors(req, env), "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, Authorization", "Access-Control-Max-Age": "600" } })
      : new Response(null, { status: 403 });
    if (path === "/api/health" && req.method === "GET") return sameOrigin(req, env) ? json({ ok: true }, 200, req, env) : json({ ok: false, error: "Không được phép." }, 403, req, env);
    if (req.method !== "POST" || !sameOrigin(req, env)) return json({ ok: false, error: "Không được phép." }, 403, req, env);
    const parsed = await parseBody(req);
    if (parsed.error) return json({ ok: false, error: parsed.error }, 400, req, env);
    const body = parsed.body;
    try {
      if (!(await limited(path, body, env))) return json({ ok: false, error: "Hệ thống tạm từ chối request. Liên hệ quản trị viên." }, 429, req, env);
      if (path === "/api/submit") {
        if (!(await secureEqual(text(body.team), env.TEAM_CODE || ""))) return json({ ok: false, error: "Mã nhóm không hợp lệ." }, 403, req, env);
        if (body.consent !== true) return json({ ok: false, error: "Bạn cần đồng ý gửi và lưu hồ sơ." }, 400, req, env);
        if (!(await verifyTurnstile(text(body.turnstileToken), req, env))) return json({ ok: false, error: "Xác minh chống bot không thành công. Hãy thử lại." }, 403, req, env);
        const record = recordFrom(body);
        if (!record || !record.name) return json({ ok: false, error: "Hồ sơ không hợp lệ hoặc quá lớn." }, 400, req, env);
        const result = await env.DB.prepare("INSERT INTO submissions (team, name, shop, data, appeal, created_at) VALUES (?, ?, ?, ?, ?, ?)").bind("team-submission", record.name, record.shop, record.data, record.appeal, new Date().toISOString()).run();
        ctx.waitUntil(purgeExpired(env));
        return json({ ok: true, id: result.meta.last_row_id }, 201, req, env);
      }
      if (!(await validMaster(req, env))) return json({ ok: false, error: "Không được phép." }, 403, req, env);
      if (path === "/api/list") {
        const { results } = await env.DB.prepare("SELECT id, name, shop, created_at FROM submissions ORDER BY id DESC LIMIT 100").all();
        ctx.waitUntil(purgeExpired(env)); return json({ ok: true, rows: results }, 200, req, env);
      }
      const id = Number.parseInt(body.id, 10);
      if (!Number.isSafeInteger(id) || id < 1) return json({ ok: false, error: "Mã hồ sơ không hợp lệ." }, 400, req, env);
      if (path === "/api/get") {
        const row = await env.DB.prepare("SELECT * FROM submissions WHERE id = ?").bind(id).first();
        if (!row) return json({ ok: false, error: "Không tìm thấy hồ sơ." }, 404, req, env);
        return json({ ok: true, row: { ...row, data: JSON.parse(row.data), appeal: JSON.parse(row.appeal) } }, 200, req, env);
      }
      if (path === "/api/delete") { await env.DB.prepare("DELETE FROM submissions WHERE id = ?").bind(id).run(); return json({ ok: true }, 200, req, env); }
      return json({ ok: false, error: "Không tìm thấy endpoint." }, 404, req, env);
    } catch (error) {
      console.error(JSON.stringify({ event: "api_error", path, message: error instanceof Error ? error.message : "unknown" }));
      return json({ ok: false, error: "Máy chủ gặp lỗi. Hãy thử lại sau." }, 500, req, env);
    }
  },
  async scheduled(_event, env, ctx) { ctx.waitUntil(purgeExpired(env)); },
};
