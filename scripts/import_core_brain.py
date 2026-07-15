"""Import luna_core_brain.json from another location into this project's brain_data."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

# Project layout: scripts/ -> parent -> my-project/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_APP_DIR = os.path.join(_PROJECT_ROOT, "my-project")
_DEFAULT_BRAIN_DIR = os.path.join(_APP_DIR, "brain_data")
_DEST_PATH = os.path.join(_DEFAULT_BRAIN_DIR, "luna_core_brain.json")


def _resolve_source(from_arg: str | None) -> str:
    if from_arg:
        path = os.path.abspath(from_arg)
        if os.path.isdir(path):
            return os.path.join(path, "luna_core_brain.json")
        return path

    env_dir = os.getenv("LUNA_BRAIN_DIR", "").strip()
    if env_dir:
        return os.path.join(os.path.abspath(env_dir), "luna_core_brain.json")

    print("No --from path and LUNA_BRAIN_DIR is not set.")
    user_input = input("Enter path to luna_core_brain.json or brain_data directory: ").strip()
    if not user_input:
        print("Aborted: no source path.", file=sys.stderr)
        sys.exit(1)
    path = os.path.abspath(user_input)
    if os.path.isdir(path):
        return os.path.join(path, "luna_core_brain.json")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Import luna_core_brain.json into local brain_data")
    parser.add_argument(
        "--from",
        dest="from_path",
        default=None,
        help="Source file or directory containing luna_core_brain.json (default: LUNA_BRAIN_DIR or prompt)",
    )
    args = parser.parse_args()

    src = _resolve_source(args.from_path)
    if not os.path.isfile(src):
        print(f"Source not found: {src}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(_DEFAULT_BRAIN_DIR, exist_ok=True)
    shutil.copy2(src, _DEST_PATH)

    with open(_DEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    knowledge = data.get("trained_knowledge", [])
    history = data.get("chat_history", [])

    print(f"Copied: {src}")
    print(f"Destination: {_DEST_PATH}")
    print(f"trained_knowledge count: {len(knowledge)}")
    print(f"chat_history count: {len(history)}")


if __name__ == "__main__":
    main()
