/**
 * Headless stack maintenance for the Windows installer and uninstaller.
 *
 * Run by NSIS under plain Node:
 *   set ELECTRON_RUN_AS_NODE=1
 *   "theFactory Mission Control.exe" maintenance.js <stop|down|purge>
 *       --deploy-dir <resources\deploy> --env <backend.env> --version <x.y.z>
 *
 * Every line on stdout is shown in the uninstaller's progress window
 * (nsExec::ExecToLog), so each step announces itself before it runs and
 * reports how it ended. Exit codes:
 *   0  done, or nothing to do (no Docker, no stack)
 *   2  bad arguments
 *   3  a step failed; the uninstaller warns but still removes the app
 *
 * Imports nothing from electron -- see factory-stack.ts.
 */

import { spawnSync } from "child_process";
import fs from "fs";
import {
  COMPOSE_PROJECT,
  imageTagForVersion,
  stackCommands,
  type StackAction,
} from "./factory-stack";

export type MaintenanceArgs = {
  action: Exclude<StackAction, "up">;
  deployDir: string;
  envPath: string;
  version: string;
};

export function parseArgs(argv: string[]): MaintenanceArgs {
  const [action, ...rest] = argv;
  if (action !== "stop" && action !== "down" && action !== "purge") {
    throw new Error(`action must be stop, down or purge (got ${action ?? "nothing"})`);
  }
  const flags = new Map<string, string>();
  for (let i = 0; i < rest.length; i += 2) {
    const flag = rest[i];
    const value = rest[i + 1];
    if (!flag?.startsWith("--") || value === undefined) {
      throw new Error(`expected --flag value pairs, got ${flag ?? ""}`);
    }
    flags.set(flag.slice(2), value);
  }
  const deployDir = flags.get("deploy-dir");
  const envPath = flags.get("env");
  const version = flags.get("version");
  if (!deployDir || !envPath || !version) {
    throw new Error("--deploy-dir, --env and --version are all required");
  }
  return { action, deployDir, envPath, version };
}

export type Runner = (args: string[]) => { status: number | null; output: string };

const dockerRunner: Runner = (args) => {
  const result = spawnSync("docker", args, { encoding: "utf-8", windowsHide: true });
  return {
    status: result.error ? null : result.status,
    output: `${result.stdout ?? ""}${result.stderr ?? ""}`.trim(),
  };
};

/** Human-readable name for one docker argv, for the progress log. */
export function describe(args: string[]): string {
  if (args[0] === "image") {
    return `Removing image ${args[args.length - 1]}`;
  }
  const verb = args.find((a) => a === "stop" || a === "down");
  if (verb === "stop") return `Stopping the ${COMPOSE_PROJECT} containers`;
  if (args.includes("--volumes")) {
    return `Removing the ${COMPOSE_PROJECT} containers and ALL factory data volumes`;
  }
  return `Removing the ${COMPOSE_PROJECT} containers (data volumes are kept)`;
}

export function runMaintenance(
  args: MaintenanceArgs,
  log: (line: string) => void,
  run: Runner = dockerRunner,
  fileExists: (p: string) => boolean = fs.existsSync,
): number {
  const probe = run(["version", "--format", "{{.Server.Version}}"]);
  if (probe.status !== 0) {
    log("Docker is not running or not installed: there is no factory stack to stop.");
    if (args.action === "purge") {
      log("WARNING: factory data volumes could not be removed. Start Docker Desktop and run");
      log(`  docker compose --project-name ${COMPOSE_PROJECT} down --volumes`);
      log("to remove them later.");
    }
    return 0;
  }
  if (!fileExists(args.envPath)) {
    // Without the generated .env compose cannot interpolate the stack, but the
    // project name alone still identifies its containers and volumes.
    log(`No backend configuration at ${args.envPath}: the factory was never started.`);
    return 0;
  }

  const commands = stackCommands(args.action, { deployDir: args.deployDir, envPath: args.envPath },
    imageTagForVersion(args.version));
  let failures = 0;
  commands.forEach((command, index) => {
    const label = `[${index + 1}/${commands.length}] ${describe(command)}`;
    log(`${label}...`);
    const result = run(command);
    const missingImage = command[0] === "image" && /No such image/i.test(result.output);
    if (result.status === 0 || missingImage) {
      log(`${label}: done`);
    } else {
      failures += 1;
      log(`${label}: FAILED (${result.output.split("\n").slice(-2).join(" ") || "no output"})`);
    }
  });
  log(failures ? `Finished with ${failures} failed step(s).` : "Finished.");
  return failures ? 3 : 0;
}

/* c8 ignore start -- process entry point */
if (require.main === module) {
  try {
    const parsed = parseArgs(process.argv.slice(2));
    process.exitCode = runMaintenance(parsed, (line) => console.log(line));
  } catch (error) {
    console.log(`theFactory maintenance: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 2;
  }
}
/* c8 ignore stop */
