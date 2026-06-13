import { spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';

const appDir = path.join(process.cwd(), 'app');
const apiDir = path.join(appDir, 'api');
const hiddenApiDir = path.join(appDir, '_api_hidden');
const nextDir = path.join(process.cwd(), '.next');

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

    // 3. Hide API directory to prevent static export errors
    if (fs.existsSync(apiDir)) {
        console.log('Hiding API directory...');
        fs.renameSync(apiDir, hiddenApiDir);
        // Verify it's gone
        if (fs.existsSync(apiDir)) {
            console.error('CRITICAL: Failed to hide API directory!');
            process.exit(1);
        }
    }

    // 4. Next build
    run('npx', ['next', 'build'], { NEXT_BUILD_TARGET: 'electron' });

    // 5. Restore API directory
    if (fs.existsSync(hiddenApiDir)) {
        console.log('Restoring API directory...');
        fs.renameSync(hiddenApiDir, apiDir);
    }

    // 6. Compile Electron TS
    run('npx', ['tsc', '--project', 'electron/tsconfig.json']);

    console.log('\nElectron build complete.');
} catch (err) {
    console.error('Build failed:', err);
    // Ensure we restore the API dir if it was hidden
    if (fs.existsSync(hiddenApiDir) && !fs.existsSync(apiDir)) {
        fs.renameSync(hiddenApiDir, apiDir);
    }
    process.exit(1);
}
