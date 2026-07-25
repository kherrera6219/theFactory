// A8 + A9 — Crash handling and offline diagnostics (Local-First Error Handling
// Standard §17, §18). Everything here is fully offline and secret-free: nothing is
// ever uploaded, and environment values / document contents are never written.

import { app, dialog } from "electron";
import { mkdirSync, writeFileSync, readFileSync, existsSync } from "fs";
import path from "path";

// %LOCALAPPDATA%\theFactory\Diagnostics on Windows (app.getPath("userData")
// resolves under %APPDATA%/%LOCALAPPDATA% per Electron platform conventions).
function diagnosticsDir(): string {
  const dir = path.join(app.getPath("userData"), "Diagnostics");
  mkdirSync(dir, { recursive: true });
  return dir;
}

// Redact anything that looks like a secret. We never log raw env values; we only
// record the *names* of secret-bearing variables so a report is reproducible
// without leaking the values themselves.
function sanitizedEnvNames(): string[] {
  const SECRET_HINT = /(KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|PRIVATE)/i;
  return Object.keys(process.env)
    .filter((name) => SECRET_HINT.test(name))
    .sort();
}

function baseDiagnostics(): Record<string, unknown> {
  return {
    generated_at: new Date().toISOString(),
    app_version: app.getVersion(),
    electron_version: process.versions.electron,
    chrome_version: process.versions.chrome,
    node_version: process.versions.node,
    platform: process.platform,
    arch: process.arch,
    // Names only — never values.
    redacted_secret_env_names: sanitizedEnvNames(),
    uploads_disabled: true,
  };
}

function atomicWriteJson(filePath: string, obj: unknown): void {
  const tmp = `${filePath}.tmp`;
  writeFileSync(tmp, JSON.stringify(obj, null, 2) + "\n", { encoding: "utf-8" });
  // fs.renameSync is atomic on the same volume (POSIX + NTFS).
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  require("fs").renameSync(tmp, filePath);
}

/**
 * A8 — Write a sanitized crash report locally and offer a safe restart.
 * Never includes secrets, env values, or document contents; never uploads.
 */
function writeCrashReport(kind: string, error: unknown): string {
  const dir = diagnosticsDir();
  const reportPath = path.join(dir, "crash-report.json");
  const err = error instanceof Error ? error : new Error(String(error));
  const report = {
    ...baseDiagnostics(),
    crash_kind: kind,
    error_name: err.name,
    error_message: err.message,
    // Stack frames can contain file paths but not secrets; keep them for debugging.
    stack: (err.stack ?? "").split("\n").slice(0, 40),
  };
  try {
    atomicWriteJson(reportPath, report);
  } catch {
    // Best-effort — a crash handler must never throw.
  }
  return reportPath;
}

/**
 * A8 — Install application-boundary handlers for uncaught exceptions and unhandled
 * promise rejections. Saves a local crash report and offers the user a safe restart.
 */
export function installCrashHandlers(): void {
  const handle = (kind: string) => (error: unknown) => {
    const reportPath = writeCrashReport(kind, error);
    try {
      const choice = dialog.showMessageBoxSync({
        type: "error",
        title: "theFactory encountered a problem",
        message: "Something went wrong and the application needs attention.",
        detail:
          `A diagnostic report was saved locally (no data was uploaded):\n${reportPath}\n\n` +
          "You can restart the application or quit.",
        buttons: ["Restart", "Quit"],
        defaultId: 0,
        cancelId: 1,
      });
      if (choice === 0) {
        app.relaunch();
      }
    } catch {
      // If the dialog itself fails, fall through to quit.
    } finally {
      app.exit(1);
    }
  };

  process.on("uncaughtException", handle("uncaughtException"));
  process.on("unhandledRejection", handle("unhandledRejection"));
}

/**
 * A9 — Generate the offline diagnostics bundle: the standard artifacts under the
 * local Diagnostics folder. Returns the folder path. Fully offline, secret-free.
 */
export function generateDiagnostics(): string {
  const dir = diagnosticsDir();

  atomicWriteJson(path.join(dir, "diagnostics.json"), baseDiagnostics());

  // integrity-report.json — placeholder structure the backend can populate later.
  atomicWriteJson(path.join(dir, "integrity-report.json"), {
    generated_at: new Date().toISOString(),
    checks: [],
    note: "Integrity checks are recorded by the orchestrator audit pipeline.",
  });

  // Ensure the expected log files exist (empty if the app hasn't written them yet)
  // so the bundle always contains the standard set named by §18.
  for (const name of ["application.log", "security.log", "audit.log"]) {
    const p = path.join(dir, name);
    if (!existsSync(p)) {
      writeFileSync(p, "", { encoding: "utf-8" });
    }
  }

  // crash-report.json is written on demand by the crash handler; reference it.
  const crashPath = path.join(dir, "crash-report.json");
  if (!existsSync(crashPath)) {
    atomicWriteJson(crashPath, { generated_at: new Date().toISOString(), crashes: "none" });
  } else {
    // touch-read to confirm readability; ignore content.
    try {
      readFileSync(crashPath, "utf-8");
    } catch {
      /* ignore */
    }
  }

  return dir;
}

export type DockerPreflightResult = {
  dockerAvailable: boolean;
  dockerRunning: boolean;
  wsl2Available: boolean;
  message: string;
};

export function checkDockerPrerequisites(): DockerPreflightResult {
  const { execSync } = require("child_process");
  try {
    const versionOutput = execSync("docker --version", { encoding: "utf-8", stdio: ["pipe", "pipe", "ignore"] });
    const dockerAvailable = String(versionOutput).includes("Docker version");

    let dockerRunning = false;
    try {
      execSync("docker info", { encoding: "utf-8", stdio: ["pipe", "pipe", "ignore"] });
      dockerRunning = true;
    } catch {
      dockerRunning = false;
    }

    let wsl2Available = false;
    if (process.platform === "win32") {
      try {
        const wslOutput = execSync("wsl --list --quiet", { encoding: "utf-8", stdio: ["pipe", "pipe", "ignore"] });
        wsl2Available = Boolean(String(wslOutput).trim());
      } catch {
        wsl2Available = false;
      }
    } else {
      wsl2Available = true;
    }

    let message = "Docker and prerequisites verified.";
    if (!dockerAvailable) {
      message = "Docker CLI not found. Please install Docker Desktop.";
    } else if (!dockerRunning) {
      message = "Docker daemon is not running. Please start Docker Desktop.";
    }

    return {
      dockerAvailable,
      dockerRunning,
      wsl2Available,
      message,
    };
  } catch {
    return {
      dockerAvailable: false,
      dockerRunning: false,
      wsl2Available: false,
      message: "Docker CLI check failed.",
    };
  }
}

