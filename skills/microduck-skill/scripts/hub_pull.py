#!/usr/bin/env python3
"""Download policy.onnx from a Hugging Face model repo. Not train. Not robotctl."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Hub policy.onnx")
    parser.add_argument("repo", help="USER/NAME")
    parser.add_argument("--out", required=True, help="Directory to place policy.onnx")
    args = parser.parse_args()
    if not REPO_RE.match(args.repo):
        print(f"microduck-skill: repo must be USER/NAME, got {args.repo!r}", file=sys.stderr)
        return 2
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("microduck-skill: huggingface_hub is missing (uv sync the RL checkout)", file=sys.stderr)
        return 2
    dest = Path(args.out).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        path = hf_hub_download(repo_id=args.repo, filename="policy.onnx", local_dir=str(dest))
    except Exception as exc:
        print(f"microduck-skill: hub pull failed for {args.repo}: {exc}", file=sys.stderr)
        return 2
    out = Path(path).resolve()
    if not out.is_file():
        print(f"microduck-skill: {args.repo} has no policy.onnx", file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
