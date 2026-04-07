import { spawn } from "node:child_process";

const args = process.argv.slice(2);

if (args.length === 0) {
  console.error("Usage: node scripts/run-npm-exec-clean-env.mjs <tool> [args...]");
  process.exit(1);
}

const env = { ...process.env };

// Some CLIs force color in child processes. When NO_COLOR is also present,
// Node emits warnings on every spawned worker/server process.
delete env.NO_COLOR;

const npmExecPath = process.env.npm_execpath;
const useNodeNpm = typeof npmExecPath === "string" && npmExecPath.length > 0;
const command = useNodeNpm ? process.execPath : process.platform === "win32" ? "npm.cmd" : "npm";
const commandArgs = useNodeNpm ? [npmExecPath, "exec", "--", ...args] : ["exec", "--", ...args];

const child = spawn(command, commandArgs, {
  cwd: process.cwd(),
  env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

child.on("error", (error) => {
  console.error(error);
  process.exit(1);
});
