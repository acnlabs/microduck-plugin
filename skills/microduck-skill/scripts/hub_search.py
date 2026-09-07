#!/usr/bin/env python3
"""List Hugging Face model repos that look like Microduck policies. Not a store."""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)


def _desc(model) -> str:
    card = getattr(model, "card_data", None) or getattr(model, "cardData", None)
    if isinstance(card, dict):
        text = card.get("description") or ""
    else:
        text = getattr(card, "description", None) or ""
    text = " ".join(str(text).split())
    return text[:80]


def _has_policy(model) -> bool:
    for sib in getattr(model, "siblings", None) or []:
        name = getattr(sib, "rfilename", None) or getattr(sib, "filename", "")
        if name == "policy.onnx":
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Hub for Microduck policy.onnx repos")
    parser.add_argument("query", nargs="?", default="microduck")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("microduck-skill: huggingface_hub is missing", file=sys.stderr)
        return 2

    query = args.query.strip() or "microduck"
    api = HfApi()
    limit = max(args.limit * 4, 40)
    try:
        found = list(
            api.list_models(
                search=query,
                expand=["siblings", "downloads", "likes", "cardData"],
                limit=limit,
            )
        )
    except TypeError:
        try:
            found = list(api.list_models(search=query, full=True, limit=limit))
        except Exception as exc:
            print(f"microduck-skill: hub search failed: {exc}", file=sys.stderr)
            return 2
    except Exception as exc:
        print(f"microduck-skill: hub search failed: {exc}", file=sys.stderr)
        return 2

    rows = []
    for model in found:
        if not _has_policy(model):
            continue
        rows.append(
            {
                "repo": model.id,
                "downloads": int(getattr(model, "downloads", 0) or 0),
                "likes": int(getattr(model, "likes", 0) or 0),
                "description": _desc(model),
            }
        )
        if len(rows) >= args.limit:
            break

    rows.sort(key=lambda r: r["repo"].lower())
    if args.json:
        print(json.dumps({"query": query, "count": len(rows), "repos": rows}, ensure_ascii=False))
        return 0
    if not rows:
        print(f"microduck-skill: no Hub repos with policy.onnx for {query!r}")
        print("microduck-skill: search is not a ranking; try another word or browse huggingface.co/models?search=microduck")
        return 0
    print(f"microduck-skill: {len(rows)} repo(s) with policy.onnx  query={query!r}")
    print("microduck-skill: downloads/likes are Hub counts, not quality. Gate + sim before robotctl.")
    print(f"{'REPO':<48} {'DL':>7} {'LIKES':>5}  DESCRIPTION")
    for row in rows:
        print(f"{row['repo']:<48} {row['downloads']:>7} {row['likes']:>5}  {row['description']}")
    print("microduck-skill: next: control.sh start --repo USER/NAME   or   pull USER/NAME --as SLOT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
