import path from "path";
import { describe, expect, it } from "vitest";
import {
  COMPOSE_PROJECT,
  SANDBOX_IMAGES,
  imageTagForVersion,
  imagesToPull,
  overallProgress,
  sandboxRetags,
  stackCommands,
} from "./factory-stack";
import { describe as describeStep, parseArgs, runMaintenance } from "./maintenance";

const PATHS = { deployDir: path.join("C:", "app", "resources", "deploy"), envPath: "C:/data/backend.env" };

describe("factory stack", () => {
  it("never shares a compose project with a developer checkout", () => {
    // `deploy` is what compose infers from the deploy/ directory in BOTH layouts.
    expect(COMPOSE_PROJECT).not.toBe("deploy");
    for (const action of ["up", "stop", "down", "purge"] as const) {
      for (const argv of stackCommands(action, PATHS, "v1.2.3")) {
        if (argv[0] === "compose") {
          expect(argv.slice(0, 3)).toEqual(["compose", "--project-name", COMPOSE_PROJECT]);
        }
      }
    }
  });

  it("starts without building and pulls every published image", () => {
    const [up] = stackCommands("up", PATHS, "v1.2.3");
    expect(up).toContain("--no-build");
    const images = imagesToPull("v1.2.3");
    expect(images).toContain("ghcr.io/kherrera6219/thefactory-orchestrator:v1.2.3");
    expect(images).toContain("ghcr.io/kherrera6219/thefactory-sandbox-csharp:v1.2.3");
    expect(images.every((image) => image.endsWith(":v1.2.3"))).toBe(true);
  });

  it("retags sandbox images to the names runtime QC runs", () => {
    const retags = new Map(sandboxRetags("v1.2.3"));
    expect(retags.get("ghcr.io/kherrera6219/thefactory-sandbox-test-java:v1.2.3")).toBe(
      "thefactory/sandbox-test-java:1",
    );
    expect(retags.size).toBe(SANDBOX_IMAGES.length);
  });

  it("keeps data volumes unless purging", () => {
    const [down] = stackCommands("down", PATHS, "v1.2.3");
    expect(down).not.toContain("--volumes");
    const [purgeDown, ...removals] = stackCommands("purge", PATHS, "v1.2.3");
    expect(purgeDown).toContain("--volumes");
    expect(removals.every((argv) => argv[0] === "image" && argv[1] === "rm")).toBe(true);
    expect(removals.map((argv) => argv[argv.length - 1])).toContain("thefactory/sandbox-test-r:1");
  });

  it("derives the image tag from the app version, and refuses anything else", () => {
    expect(imageTagForVersion("1.4.0")).toBe("v1.4.0");
    expect(imageTagForVersion("v1.4.0-rc.1")).toBe("v1.4.0-rc.1");
    expect(() => imageTagForVersion("latest")).toThrow();
  });

  it("maps startup steps to a monotonic 0-100 progress", () => {
    const points = [
      overallProgress("docker"),
      overallProgress("images", 0),
      overallProgress("images", 0.5),
      overallProgress("images", 1),
      overallProgress("health", 1),
    ];
    expect(points).toEqual([...points].sort((a, b) => a - b));
    expect(points[points.length - 1]).toBe(100);
    expect(overallProgress("images", 7)).toBe(80);
  });
});

describe("uninstall maintenance", () => {
  const args = ["down", "--deploy-dir", PATHS.deployDir, "--env", PATHS.envPath, "--version", "1.2.3"];

  it("parses the NSIS command line", () => {
    expect(parseArgs(args)).toEqual({
      action: "down",
      deployDir: PATHS.deployDir,
      envPath: PATHS.envPath,
      version: "1.2.3",
    });
    expect(() => parseArgs(["up", ...args.slice(1)])).toThrow(/stop, down or purge/);
    expect(() => parseArgs(["down", "--env"])).toThrow();
  });

  it("does nothing and succeeds when Docker is absent", () => {
    const log: string[] = [];
    const ran: string[][] = [];
    const code = runMaintenance(parseArgs(args), (l) => log.push(l), (argv) => {
      ran.push(argv);
      return { status: null, output: "" };
    });
    expect(code).toBe(0);
    expect(ran).toHaveLength(1); // only the probe
    expect(log.join("\n")).toMatch(/no factory stack/);
  });

  it("warns that purge could not remove data when Docker is absent", () => {
    const log: string[] = [];
    runMaintenance(parseArgs(["purge", ...args.slice(1)]), (l) => log.push(l), () => ({
      status: 1,
      output: "",
    }));
    expect(log.join("\n")).toMatch(/could not be removed/);
  });

  it("reports each step and treats an already-removed image as done", () => {
    const log: string[] = [];
    const code = runMaintenance(
      parseArgs(["purge", ...args.slice(1)]),
      (l) => log.push(l),
      (argv) => (argv[0] === "image"
        ? { status: 1, output: "Error: No such image: x" }
        : { status: 0, output: "" }),
      () => true,
    );
    expect(code).toBe(0);
    expect(log.some((l) => /ALL factory data volumes/.test(l))).toBe(true);
    expect(log[log.length - 1]).toBe("Finished.");
  });

  it("exits 3 when a step fails, naming it", () => {
    const log: string[] = [];
    const code = runMaintenance(parseArgs(args), (l) => log.push(l),
      (argv) => (argv[0] === "version" ? { status: 0, output: "29.0" } : { status: 1, output: "boom" }),
      () => true);
    expect(code).toBe(3);
    expect(log.join("\n")).toMatch(/FAILED \(boom\)/);
  });

  it("skips cleanly when the app was never started", () => {
    const log: string[] = [];
    const code = runMaintenance(parseArgs(args), (l) => log.push(l),
      () => ({ status: 0, output: "" }), () => false);
    expect(code).toBe(0);
    expect(log.join("\n")).toMatch(/never started/);
  });

  it("describes steps in operator language", () => {
    expect(describeStep(["compose", "stop"])).toMatch(/Stopping/);
    expect(describeStep(["image", "rm", "--force", "x:1"])).toBe("Removing image x:1");
  });
});
