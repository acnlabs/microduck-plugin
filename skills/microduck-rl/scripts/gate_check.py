#!/usr/bin/env python3
"""Refuse an ONNX policy that is not [1, 61] -> [1, 14].

Skip initializer names (older IR lists them on graph.input). Official
`uv run publish` already gates shape / NaN / constant output; this is a
pre-publish check. Run via: uv run --with onnx python3 gate_check.py FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _dim(d) -> int | None:
    if d is None:
        return None
    if isinstance(d, int):
        return d
    dim_value = getattr(d, "dim_value", None)
    if dim_value is not None:
        return int(dim_value)
    if isinstance(d, dict) and "dim_value" in d:
        return int(d["dim_value"])
    return None


def _shape_of(vi) -> list[int | None]:
    tt = getattr(vi, "type", None)
    tensor = getattr(tt, "tensor_type", None) if tt is not None else None
    if tensor is None and isinstance(tt, dict):
        tensor = tt.get("tensor_type")
    if tensor is None:
        return []
    shape = getattr(tensor, "shape", None)
    if shape is None and isinstance(tensor, dict):
        shape = tensor.get("shape")
    dims = getattr(shape, "dim", None) if shape is not None else None
    if dims is None and isinstance(shape, dict):
        dims = shape.get("dim", [])
    return [_dim(d) for d in (dims or [])]


def _external_ios(graph):
    init_names = {init.name for init in graph.initializer}
    inputs = [i for i in graph.input if i.name not in init_names]
    outputs = list(graph.output)
    return inputs, outputs


def inspect(path: Path) -> dict:
    try:
        import onnx  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "microduck-rl: need `onnx`. Use: uv run --with onnx python3 "
            f"scripts/gate_check.py  ({exc})"
        ) from exc

    model = onnx.load(str(path))
    inputs, outputs = _external_ios(model.graph)
    return {
        "file": str(path),
        "inputs": [{"name": i.name, "shape": _shape_of(i)} for i in inputs],
        "outputs": [{"name": o.name, "shape": _shape_of(o)} for o in outputs],
    }


def ok_shape(shape: list[int | None], expected: list[int]) -> bool:
    if len(shape) != len(expected):
        return False
    for got, want in zip(shape, expected):
        if got is None:
            continue
        if got != want:
            return False
    return True


def pick_io(entries: list[dict], expected: list[int], kind: str) -> list[int | None]:
    if not entries:
        print(f"microduck-rl: graph has no {kind}", file=sys.stderr)
        raise SystemExit(1)
    for item in entries:
        if ok_shape(item["shape"], expected):
            return item["shape"]
    return entries[0]["shape"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("onnx", type=Path)
    args = p.parse_args()
    if not args.onnx.is_file():
        print(f"microduck-rl: not a file: {args.onnx}", file=sys.stderr)
        return 2

    info = inspect(args.onnx)
    print(json.dumps(info, indent=2))

    inn = pick_io(info["inputs"], [1, 61], "inputs")
    out = pick_io(info["outputs"], [1, 14], "outputs")
    if not ok_shape(inn, [1, 61]) or not ok_shape(out, [1, 14]):
        print(
            "microduck-rl: refused — expected [1,61] -> [1,14], "
            f"got {inn} -> {out}. Use scripts/export.py; never hand-convert.",
            file=sys.stderr,
        )
        return 1

    print("microduck-rl: gate ok ([1,61] -> [1,14])")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
