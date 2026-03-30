const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);
const TRUSTED_FETCH_SITES = new Set(["", "same-origin", "same-site", "none"]);

function parseUrl(value: string | null): URL | null {
  if (!value) {
    return null;
  }
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function isLocalHost(hostname: string): boolean {
  return LOCAL_HOSTS.has(hostname.trim().toLowerCase());
}

function normalizedPort(url: URL): string {
  if (url.port) {
    return url.port;
  }
  return url.protocol === "https:" ? "443" : "80";
}

function isTrustedLocalBrowserRequest(request: Request): boolean {
  const requestUrl = parseUrl(request.url);
  const originUrl =
    parseUrl(request.headers.get("origin")) ?? parseUrl(request.headers.get("referer"));
  const fetchSite = request.headers.get("sec-fetch-site")?.trim().toLowerCase() ?? "";

  if (!requestUrl || !originUrl) {
    return false;
  }

  if (!isLocalHost(requestUrl.hostname) || !isLocalHost(originUrl.hostname)) {
    return false;
  }

  if (
    originUrl.protocol !== requestUrl.protocol ||
    normalizedPort(originUrl) !== normalizedPort(requestUrl)
  ) {
    return false;
  }

  return TRUSTED_FETCH_SITES.has(fetchSite);
}

export function isAuthorizedVaultRequest(request: Request): boolean {
  const adminKey = process.env.VAULT_ADMIN_KEY?.trim() ?? "";
  const header = request.headers.get("x-vault-admin-key")?.trim() ?? "";

  if (adminKey && header.length > 0 && header === adminKey) {
    return true;
  }

  return isTrustedLocalBrowserRequest(request);
}
