import { spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';

// Electron used to build via static export, which required physically hiding
// app/api before the build (Next's static export cannot contain dynamic App
// Router routes) and restoring it after. That meant none of this app's 14
// app/api/* routes (vault, session, gateway proxy, repo import, etc.) worked
// in the packaged app -- see docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md §7.1.
// Electron now builds with `output: "standalone"` (set in next.config.mjs
// when NEXT_BUILD_TARGET=electron) instead, producing a self-contained
// server.js that electron/main.ts spawns as a child process. No API-route
// hiding needed -- the standalone server supports all of them.
const nextDir = path.join(process.cwd(), '.next');
const standaloneDir = path.join(nextDir, 'standalone');

function run(cmd, args, env = {}) {
    console.log(`Running: ${cmd} ${args.join(' ')}`);
    const res = spawnSync(cmd, args, {
        env: { ...process.env, ...env },
        stdio: 'inherit',
        shell: true,
    });
    if (res.status !== 0) {
        process.exit(res.status || 1);
    }
}

try {
    // 1. Sync tokens
    run('npm', ['run', 'tokens:sync']);

    // 2. Clean previous build artifacts
    if (fs.existsSync(nextDir)) {
        console.log('Cleaning .next directory...');
        fs.rmSync(nextDir, { recursive: true, force: true });
    }

    // 3. Next build (standalone output via NEXT_BUILD_TARGET=electron)
    run('npx', ['next', 'build'], { NEXT_BUILD_TARGET: 'electron' });

    if (!fs.existsSync(standaloneDir)) {
        console.error(
            `CRITICAL: expected standalone output at ${standaloneDir} -- ` +
            'check next.config.mjs sets output:"standalone" for NEXT_BUILD_TARGET=electron.',
        );
        process.exit(1);
    }

    // 4. Next's standalone output intentionally excludes static assets and
    // public/ -- copy them in so the embedded server can serve them (this is
    // Next.js's own documented standalone-deployment step, not specific to
    // Electron).
    console.log('Assembling standalone server bundle...');
    fs.cpSync(path.join(process.cwd(), 'public'), path.join(standaloneDir, 'public'), {
        recursive: true,
    });
    fs.cpSync(path.join(nextDir, 'static'), path.join(standaloneDir, '.next', 'static'), {
        recursive: true,
    });

    // 5. Compile Electron TS
    run('npx', ['tsc', '--project', 'electron/tsconfig.json']);

    // 6. tsc only compiles .ts -- copy the first-run wizard's static HTML
    // pages alongside the compiled preload scripts that reference them.
    const electronOutDir = path.join(process.cwd(), 'dist', 'electron', 'electron');
    for (const htmlFile of ['setup-wizard.html', 'starting.html']) {
        fs.copyFileSync(
            path.join(process.cwd(), 'electron', htmlFile),
            path.join(electronOutDir, htmlFile),
        );
    }

    console.log('\nElectron build complete.');
} catch (err) {
    console.error('Build failed:', err);
    process.exit(1);
}
