from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT))

from orchestrator.agent_registry import AGENT_REGISTRY  # noqa: E402

from shared_runtime.atomic_io import atomic_write_text  # noqa: E402


def _env_name(agent_id: str) -> str:
    return f"{agent_id.replace('-', '_')}_SERVICE_API_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a local ignored env file with per-agent "
            "and internal service API keys."
        )
    )
    parser.add_argument(
        "--output-file",
        default=".env.agent-service-keys.local",
        help="Ignored env file path for generated service keys.",
    )
    parser.add_argument(
        "--mode",
        default="strict",
        choices=("shared", "strict"),
        help="Global AGENT_SERVICE_KEY_MODE value to emit.",
    )
    parser.add_argument(
        "--key-length-bytes",
        type=int,
        default=24,
        help="Random secret byte length before urlsafe encoding.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output_file)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    if output_path.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing file: {output_path}")

    lines = [
        "# Generated local per-agent service keys",
        "# Do not commit this file.",
        f"AGENT_SERVICE_KEY_MODE={args.mode}",
        f"INTERNAL_SERVICE_API_KEY=hgr-internal-{secrets.token_urlsafe(args.key_length_bytes)}",
        "",
    ]

    for agent in AGENT_REGISTRY:
        lines.append(
            f"{_env_name(agent.agent_id)}=hgr-{agent.agent_id.lower()}-{secrets.token_urlsafe(args.key_length_bytes)}"
        )

    atomic_write_text(output_path, "\n".join(lines) + "\n")
    label = output_path.relative_to(ROOT) if output_path.is_relative_to(ROOT) else output_path
    print(f"wrote {len(AGENT_REGISTRY)} agent service keys to {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
