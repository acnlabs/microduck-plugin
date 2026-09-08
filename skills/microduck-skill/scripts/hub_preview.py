#!/usr/bin/env python3
"""Attach preview.mp4 to a Hub policy card. Checkpoint replay, not ONNX, not robotctl."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PREVIEW_NAME = "preview.mp4"
BEGIN = "<!-- microduck-skill:preview -->"
END = "<!-- /microduck-skill:preview -->"


def preview_src(repo: str) -> str:
    return f"https://huggingface.co/{repo}/resolve/main/{PREVIEW_NAME}"


def preview_body(repo: str) -> str:
    src = preview_src(repo)
    return f"""## Preview

<video controls muted loop width="100%">
  <source src="{src}" type="video/mp4">
</video>

Sim checkpoint replay (`play.sh`). Not the ONNX runtime path, not a real robot, not an official Pollen policy.
"""


def embed_preview(readme: str, repo: str) -> str:
    if not REPO_RE.match(repo):
        raise ValueError(f"repo must be USER/NAME, got {repo!r}")
    block = f"{BEGIN}\n{preview_body(repo).strip()}\n{END}\n"
    if BEGIN in readme and END in readme:
        pre, rest = readme.split(BEGIN, 1)
        _, post = rest.split(END, 1)
        tail = post.lstrip("\n")
        return f"{pre}{block}{tail}"
    if readme.startswith("---"):
        parts = readme.split("---", 2)
        if len(parts) >= 3:
            return f"---{parts[1]}---\n\n{block}\n{parts[2].lstrip()}"
    if not readme.strip():
        return block
    return f"{block}\n{readme.lstrip()}"


def find_play_mp4(rl_root: Path, *, since: float | None = None) -> Path | None:
    root = Path(rl_root)
    hits = {p.resolve() for p in root.glob("logs/**/videos/play/*.mp4") if p.is_file()}
    if not hits:
        hits = {p.resolve() for p in root.glob("**/videos/play/*.mp4") if p.is_file()}
    ordered = sorted(hits, key=lambda p: p.stat().st_mtime, reverse=True)
    if since is None:
        return ordered[0] if ordered else None
    for path in ordered:
        if path.stat().st_mtime >= since - 1:
            return path
    return None


def upload_preview(repo: str, mp4: Path) -> None:
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    api.upload_file(
        path_or_fileobj=str(mp4),
        path_in_repo=PREVIEW_NAME,
        repo_id=repo,
        repo_type="model",
        commit_message="docs: add sim checkpoint preview",
    )
    try:
        readme_path = hf_hub_download(
            repo_id=repo,
            filename="README.md",
            repo_type="model",
            force_download=True,
        )
        text = Path(readme_path).read_text(encoding="utf-8")
    except Exception as exc:
        name = type(exc).__name__
        if name in {"EntryNotFoundError", "HfHubHTTPError"} and "404" in str(exc):
            text = ""
        else:
            raise
    updated = embed_preview(text, repo)
    if updated != text:
        tmp = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", suffix=".md", delete=False
            ) as fh:
                fh.write(updated)
                tmp = fh.name
            api.upload_file(
                path_or_fileobj=tmp,
                path_in_repo="README.md",
                repo_id=repo,
                repo_type="model",
                commit_message="docs: embed sim checkpoint preview",
            )
        finally:
            if tmp:
                os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload preview.mp4 to a Hub policy card")
    parser.add_argument("--repo", help="USER/NAME")
    parser.add_argument("--mp4", help="Local checkpoint replay clip")
    parser.add_argument("--find-root", help="Print newest play mp4 under this tree and exit")
    parser.add_argument("--since", type=float, default=None, help="With --find-root, only clips newer than this unix time")
    args = parser.parse_args()
    if args.find_root:
        found = find_play_mp4(Path(args.find_root), since=args.since)
        if found is None:
            print("microduck-skill: no play mp4 under logs/**/videos/play/", file=sys.stderr)
            return 2
        print(found)
        return 0
    if not args.repo or not args.mp4:
        print("microduck-skill: need --repo and --mp4 (or --find-root)", file=sys.stderr)
        return 2
    if not REPO_RE.match(args.repo):
        print(f"microduck-skill: repo must be USER/NAME, got {args.repo!r}", file=sys.stderr)
        return 2
    mp4 = Path(args.mp4).expanduser().resolve()
    if not mp4.is_file():
        print(f"microduck-skill: not a file: {mp4}", file=sys.stderr)
        return 2
    try:
        upload_preview(args.repo, mp4)
    except Exception as exc:
        print(f"microduck-skill: preview upload failed for {args.repo}: {exc}", file=sys.stderr)
        return 2
    print(f"https://huggingface.co/{args.repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
