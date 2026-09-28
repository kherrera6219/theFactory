/**
 * The installed factory's Docker stack, described without Electron.
 *
 * Everything the desktop app and the uninstaller need to agree on lives here:
 * the compose project name, which files and env to use, which images to pull,
 * and the exact argv for each lifecycle action. It imports nothing from
 * `electron`, so the uninstaller runs it under plain Node
 * (`ELECTRON_RUN_AS_NODE=1`, see maintenance.ts) and Vitest can test it.
 */

import path from "path";

/**
 * Compose project for the INSTALLED app. Deliberately not "deploy": compose
 * derives a default project name from the compose file's directory, which is
 * `deploy/` in both a developer checkout and the packaged resources. Sharing it
 * would let the installed app's uninstaller (`down -v`) delete a developer's
 * own stack and data.
 */
export const COMPOSE_PROJECT = "thefactory-app";

/** Registry the release workflow publishes to (see .github/workflows/release.yml). */
export const DEFAULT_IMAGE_REGISTRY = "ghcr.io/kherrera6219";

/**
 * Factory images published per release, and -- for the sandbox runners --
 * the local name runtime QC looks for. Runtime QC names its images
 * `thefactory/sandbox-*` (rqca_agent._VENDORED_TEST_RUNTIMES); the installer
 * pulls them from the registry and tags them under that name.
 */
export const SERVICE_IMAGES = [
  "orchestrator",
  "api-gateway",
  "protocol-bus-mcp",
  "dashboard",
  "pod-worker",
  "audit-worker",
  "mission-control",
] as const;

export const SANDBOX_IMAGES: ReadonlyArray<{ published: string; local: string }> = [
  { published: "sandbox-test-python", local: "thefactory/sandbox-test-python:1" },
  { published: "sandbox-test-java", local: "thefactory/sandbox-test-java:1" },
  { published: "sandbox-test-kotlin", local: "thefactory/sandbox-test-kotlin:1" },
  { published: "sandbox-test-scala", local: "thefactory/sandbox-test-scala:1" },
  { published: "sandbox-test-php", local: "thefactory/sandbox-test-php:1" },
  { published: "sandbox-test-r", local: "thefactory/sandbox-test-r:1" },
  { published: "sandbox-test-node", local: "thefactory/sandbox-test-node:1" },
  { published: "sandbox-csharp", local: "thefactory/sandbox-csharp:1" },
];

export type StackPaths = {
  /** Directory holding docker-compose.yaml and docker-compose.installer.yaml. */
  deployDir: string;
  /** The generated backend .env. */
  envPath: string;
};

/** Release tag the images were published under: "v" + the app version. */
export function imageTagForVersion(appVersion: string): string {
  const version = appVersion.trim().replace(/^v/i, "");
  if (!/^\d+\.\d+\.\d+([-.+][0-9A-Za-z.-]+)?$/.test(version)) {
    throw new Error(`Not a release version: ${appVersion}`);
  }
  return `v${version}`;
}

export function publishedImage(name: string, tag: string, registry = DEFAULT_IMAGE_REGISTRY): string {
  return `${registry.replace(/\/+$/, "")}/thefactory-${name}:${tag}`;
}

/** Every image a first run pulls, in the order the progress window shows. */
export function imagesToPull(tag: string, registry = DEFAULT_IMAGE_REGISTRY): string[] {
  return [
    ...SERVICE_IMAGES.map((name) => publishedImage(name, tag, registry)),
    ...SANDBOX_IMAGES.map((image) => publishedImage(image.published, tag, registry)),
  ];
}

/** `docker tag` pairs that give runtime QC its expected sandbox image names. */
export function sandboxRetags(
  tag: string,
  registry = DEFAULT_IMAGE_REGISTRY,
): Array<[string, string]> {
  return SANDBOX_IMAGES.map((image) => [publishedImage(image.published, tag, registry), image.local]);
}

/** Leading `docker compose ...` arguments shared by every action. */
export function composeBase(paths: StackPaths): string[] {
  return [
    "compose",
    "--project-name", COMPOSE_PROJECT,
    "--env-file", paths.envPath,
    "--project-directory", paths.deployDir,
    "-f", path.join(paths.deployDir, "docker-compose.yaml"),
    "-f", path.join(paths.deployDir, "docker-compose.installer.yaml"),
  ];
}

export type StackAction = "up" | "stop" | "down" | "purge";

/**
 * Argv lists (each run as `docker <argv>`) for a lifecycle action.
 *
 * - up    start containers; never builds (--no-build), pulls are done first,
 *         one image at a time, so the progress window can count them.
 * - stop  stop containers, keep them and all data.
 * - down  remove containers and the network; KEEP volumes (the default
 *         uninstall: missions, vault and audit evidence survive a reinstall).
 * - purge remove containers, volumes, and the factory's own images.
 */
export function stackCommands(action: StackAction, paths: StackPaths, tag: string): string[][] {
  const base = composeBase(paths);
  switch (action) {
    case "up":
      return [[...base, "up", "-d", "--no-build", "--remove-orphans"]];
    case "stop":
      return [[...base, "stop"]];
    case "down":
      return [[...base, "down", "--remove-orphans"]];
    case "purge":
      return [
        [...base, "down", "--volumes", "--remove-orphans"],
        ...imagesToPull(tag).map((image) => ["image", "rm", "--force", image]),
        ...SANDBOX_IMAGES.map((image) => ["image", "rm", "--force", image.local]),
      ];
    default: {
      const unreachable: never = action;
      throw new Error(`Unknown stack action: ${String(unreachable)}`);
    }
  }
}

/** Steps shown in the first-run / startup progress window, in order. */
export const STARTUP_STEPS = [
  { id: "docker", label: "Check Docker Desktop" },
  { id: "configure", label: "Prepare configuration" },
  { id: "images", label: "Download factory images" },
  { id: "start", label: "Start services" },
  { id: "health", label: "Wait for services to report healthy" },
] as const;

export type StartupStepId = (typeof STARTUP_STEPS)[number]["id"];

/**
 * Overall 0-100 progress. Image downloads dominate a first run, so they get
 * the widest band; every other step is a fixed slice.
 */
export function overallProgress(step: StartupStepId, fraction = 0): number {
  const bands: Record<StartupStepId, [number, number]> = {
    docker: [0, 5],
    configure: [5, 10],
    images: [10, 80],
    start: [80, 90],
    health: [90, 100],
  };
  const [start, end] = bands[step];
  const bounded = Math.min(1, Math.max(0, fraction));
  return Math.round(start + (end - start) * bounded);
}

export type FactoryHealth = "running" | "starting" | "stopped" | "unreachable";

/** Tray wording for a health state. */
export function healthLabel(health: FactoryHealth): string {
  switch (health) {
    case "running":
      return "Factory running";
    case "starting":
      return "Factory starting…";
    case "stopped":
      return "Factory stopped";
    default:
      return "Factory not reachable";
  }
}

/**
 * The standalone server must run from a real directory. Inside the packaged
 * app, `app.getAppPath()` is `resources\app.asar` -- an archive file -- and a
 * child process cannot use a path inside it as its working directory: spawn
 * fails with ENOENT naming the executable, which is what crashed the first
 * installed build (2026-09-27). package.json build.asarUnpack extracts the
 * server to `resources\app.asar.unpacked`; prefer that.
 */
export function standaloneServerCandidates(appPath: string, cwd: string): string[] {
  const unpacked = appPath.replace(/app\.asar$/, "app.asar.unpacked");
  return [
    path.join(unpacked, ".next", "standalone", "server.js"),
    path.join(appPath, ".next", "standalone", "server.js"),
    path.join(cwd, ".next", "standalone", "server.js"),
  ];
}

/** Parses KEY=value lines (no expansion; comments and blanks ignored). */
export function parseEnvText(text: string): Record<string, string> {
  const values: Record<string, string> = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    values[line.slice(0, eq).trim()] = line.slice(eq + 1).trim().replace(/^"(.*)"$/, "$1");
  }
  return values;
}

/** Secrets the Mission Control container receives, mirrored for the embedded server. */
export const EMBEDDED_SERVER_SECRETS = [
  "INTERNAL_SERVICE_API_KEY",
  "MISSION_CONTROL_ADMIN_KEY",
  "MISSION_CONTROL_SESSION_SECRET",
  "VAULT_ADMIN_KEY",
  "APPROVAL_HMAC_SECRET",
] as const;

export function gatewayBaseUrl(backend: Record<string, string>): string {
  return `http://localhost:${backend.API_GATEWAY_HOST_PORT || "8100"}`;
}

/**
 * Environment for the desktop app's embedded Next.js server, equivalent to the
 * mission-control container's (deploy/docker-compose.yaml) but addressed from
 * the host: services by their published localhost ports, and the vault file in
 * the app's own data folder rather than %USERPROFILE%\.thefactory, which a
 * developer's Mission Control may also use. Without this the embedded server
 * held no key, so every gateway call was refused and the home page reported
 * "Mission metrics are unavailable" on a working install.
 */
export function embeddedServerEnv(
  backend: Record<string, string>,
  vaultDataPath: string,
): Record<string, string> {
  const env: Record<string, string> = {
    MISSION_API_BASE_URL: gatewayBaseUrl(backend),
    NEXT_PUBLIC_API_BASE_URL: gatewayBaseUrl(backend),
    ORCHESTRATOR_INTERNAL_BASE_URL: `http://localhost:${backend.ORCHESTRATOR_HOST_PORT || "8101"}`,
    // A single local operator on their own desktop, served over localhost:
    // the same settings the bundled container runs with.
    OPERATOR_SESSION_BYPASS: "true",
    MISSION_CONTROL_SESSION_SECURE: "false",
    VAULT_DATA_PATH: vaultDataPath,
  };
  for (const key of EMBEDDED_SERVER_SECRETS) {
    if (backend[key]) env[key] = backend[key];
  }
  return env;
}
