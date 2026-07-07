import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { getActiveLlmRoute, getVaultSecret } from "../../../lib/server/vault";

const DEFAULT_GATEWAY_BASE = "http://127.0.0.1:8100";
const gatewayBase = (process.env.MISSION_API_BASE_URL ?? DEFAULT_GATEWAY_BASE).trim();

// Server-side internal service key — used for /internal/* routes that require
// orchestrator-level auth rather than a user-facing operator key.
const INTERNAL_SERVICE_API_KEY = (process.env.INTERNAL_SERVICE_API_KEY ?? "").trim();

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

function targetUrl(pathSegments: string[] | undefined, requestUrl: string): string {
  const request = new URL(requestUrl);
  const target = new URL(pathSegments?.join("/") ?? "", gatewayBase.endsWith("/") ? gatewayBase : `${gatewayBase}/`);
  target.search = request.search;
  return target.toString();
}

function forwardedHeaders(request: Request): Headers {
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");
  return headers;
}

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  // This catch-all proxy is the path the browser client uses for nearly all
  // backend traffic (see lib/api-client.ts), including mission creation and
  // /internal/* routes -- unlike every sibling privileged route in this app
  // (local/*, repo/*), it previously had no operator-session gate at all, so
  // any caller able to reach this Next.js server could create/list/modify
  // missions with no Mission Control session, since the route injects the
  // operator/internal API key itself regardless of caller identity.
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  const { path } = await context.params;
  const method = request.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();

  const headers = forwardedHeaders(request);

  // Tracks whether we injected a vault operator key that differs from the
  // internal service key, so we can self-heal if the gateway rejects it. A
  // stale OPERATOR-API-KEY left in the local vault from a prior session (after
  // backend keys are rotated) would otherwise break every operator route.
  let injectedStaleableOperatorKey = false;

  if (!headers.has("x-api-key")) {
    // /internal/* routes are orchestrator-internal and require INTERNAL_SERVICE_API_KEY.
    const isInternalRoute = Array.isArray(path) && path[0] === "internal";
    const operatorKey = await getVaultSecret("OPERATOR-API-KEY");

    if (isInternalRoute && INTERNAL_SERVICE_API_KEY) {
      // Hard requirement: orchestrator-internal routes MUST use the internal key.
      headers.set("x-api-key", INTERNAL_SERVICE_API_KEY);
    } else if (operatorKey) {
      // User-facing route with a vault key configured.
      headers.set("x-api-key", operatorKey);
      injectedStaleableOperatorKey =
        Boolean(INTERNAL_SERVICE_API_KEY) && operatorKey !== INTERNAL_SERVICE_API_KEY;
    } else if (INTERNAL_SERVICE_API_KEY) {
      // Local unlocked mode: no vault key, fallback to internal key for everything.
      headers.set("x-api-key", INTERNAL_SERVICE_API_KEY);
    }
  }

  let requestBody = body;
  if (method === "POST" && path && path.length === 2 && path[0] === "v1" && path[1] === "missions" && body) {
    try {
      const decoder = new TextDecoder("utf-8");
      const text = decoder.decode(body);
      const payload = JSON.parse(text);

      const geminiKey = await getVaultSecret("GEMINI-API-KEY");
      const openaiKey = await getVaultSecret("OPENAI-API-KEY");
      const anthropicKey = await getVaultSecret("ANTHROPIC-API-KEY");
      const activeRoute = await getActiveLlmRoute();

      payload.metadata = payload.metadata || {};
      payload.metadata.vault = {
        gemini_api_key: geminiKey || "",
        openai_api_key: openaiKey || "",
        anthropic_api_key: anthropicKey || "",
        // Operator's Settings-selected primary provider/model (falls back to
        // the orchestrator's own .env defaults when unset).
        ...(activeRoute
          ? { llm_provider: activeRoute.provider, llm_model: activeRoute.model }
          : {}),
      };

      const encoder = new TextEncoder();
      requestBody = encoder.encode(JSON.stringify(payload)).buffer;
    } catch (err) {
      console.error("Failed to inject vault secrets in proxy route:", err);
    }
  }

  try {
    let upstream = await fetch(targetUrl(path, request.url), {
      method,
      headers,
      body: requestBody,
      cache: "no-store",
    });

    // Self-heal: if the gateway rejected a stale operator key from the local
    // vault (401/403), retry once with the internal service key, which is always
    // valid in local mode. Prevents a leftover OPERATOR-API-KEY from silently
    // breaking the operations/databases views after backend keys rotate.
    if (
      injectedStaleableOperatorKey &&
      (upstream.status === 401 || upstream.status === 403) &&
      INTERNAL_SERVICE_API_KEY
    ) {
      const retryHeaders = new Headers(headers);
      retryHeaders.set("x-api-key", INTERNAL_SERVICE_API_KEY);
      upstream = await fetch(targetUrl(path, request.url), {
        method,
        headers: retryHeaders,
        body: requestBody,
        cache: "no-store",
      });
    }

    // Forward the upstream response verbatim, preserving its HTTP status code
    // so callers can branch on it (404 → 404, 500 → 500, 503 → 503). The body
    // is streamed through unchanged for both success and error responses.
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    // The backend is unreachable (connection refused, DNS failure, timeout).
    // Report it as a genuine 503 so the client treats it as a service outage.
    return Response.json(
      {
        detail:
          "Local runtime gateway is unavailable. Start the runtime or update MISSION_API_BASE_URL to enable live data.",
      },
      { status: 503 },
    );
  }
}

export async function GET(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxy(request, context);
}
