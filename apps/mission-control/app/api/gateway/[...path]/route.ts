export const dynamic = "force-dynamic";

const DEFAULT_GATEWAY_BASE = "http://localhost:8100";
const gatewayBase = process.env.MISSION_API_BASE_URL ?? DEFAULT_GATEWAY_BASE;

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
  const { path } = await context.params;
  const method = request.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();

  try {
    const upstream = await fetch(targetUrl(path, request.url), {
      method,
      headers: forwardedHeaders(request),
      body,
      cache: "no-store",
    });

    if (!upstream.ok) {
      let detail = "Local runtime gateway returned an error.";
      try {
        const payload = (await upstream.clone().json()) as { detail?: unknown };
        if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
          detail = payload.detail;
        }
      } catch {
        detail = upstream.statusText || detail;
      }
      return Response.json(
        {
          __gateway_error: true,
          status: upstream.status,
          detail,
        },
        { status: 200 },
      );
    }

    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        __gateway_error: true,
        status: 503,
        detail:
          "Local runtime gateway is unavailable. Start the runtime or update MISSION_API_BASE_URL to enable live data.",
      },
      { status: 200 },
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
