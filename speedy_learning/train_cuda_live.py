from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from backend.skeleton_map import RAW17_EDGES
from models.movement_classification import GraphBiasedSTTransformer, ModelCfg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train full CUDA model from transformed JSONL dataset")
    parser.add_argument("--data-root", default="datasets")
    parser.add_argument("--out-dir", default="datasets/training_outputs")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-2)
    parser.add_argument("--window", type=int, default=120)
    parser.add_argument("--step", type=int, default=30)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--eval-every-batches", type=int, default=10)
    parser.add_argument("--save-every-epochs", type=int, default=5)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--label-smoothing", type=float, default=0.05)
    parser.add_argument("--scheduler", choices=["cosine", "none"], default="cosine")
    parser.add_argument("--warmup-epochs", type=int, default=5)
    parser.add_argument("--min-lr", type=float, default=1e-5)
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def extract_transformed_17x7(record: dict[str, Any]) -> np.ndarray:
    transformed = record.get("pose_raw17_transformed")
    if not isinstance(transformed, dict):
        raise ValueError("pose_raw17_transformed missing")

    joints = transformed.get("joints")
    if not isinstance(joints, list) or len(joints) != 17:
        raise ValueError("pose_raw17_transformed.joints must have length 17")

    rows: list[list[float]] = []
    for idx, joint in enumerate(joints):
        if not isinstance(joint, dict):
            raise ValueError(f"pose_raw17_transformed.joints[{idx}] invalid type")
        try:
            x = float(joint["x"])
            y = float(joint["y"])
            z = float(joint["z"])
        except Exception as exc:
            raise ValueError(f"pose_raw17_transformed.joints[{idx}] missing/invalid xyz") from exc
        rows.append([x, y, z, 1.0, 0.0, 0.0, 0.0])
    return np.asarray(rows, dtype=np.float32)


def load_video_frames(video_jsonl_path: Path) -> list[np.ndarray]:
    lines = video_jsonl_path.read_text(encoding="utf-8").splitlines()
    out: list[np.ndarray] = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except Exception as exc:
            raise ValueError(f"invalid json in {video_jsonl_path} line {i+1}") from exc
        out.append(extract_transformed_17x7(record))
    if not out:
        raise ValueError(f"no frames parsed from {video_jsonl_path}")
    return out


def infer_label_name_from_stem(stem: str) -> str:
    m = re.match(r"^(.*?)(?:_?\d+)$", stem)
    if m and m.group(1):
        return m.group(1).rstrip("_")
    return stem


def build_padded_sequences(
    frames: list[np.ndarray],
    label_id: int,
    label_name: str,
    video_name: str,
    window: int,
    step: int,
    source_path: str,
) -> list[dict[str, Any]]:
    sequences: list[dict[str, Any]] = []
    n = len(frames)

    if n <= window:
        pad_count = window - n
        base = np.stack(frames, axis=0)
        if pad_count > 0:
            last = frames[-1][None, ...]
            pad = np.repeat(last, repeats=pad_count, axis=0)
            x = np.concatenate([base, pad], axis=0)
            mask = np.concatenate([np.ones(n, dtype=np.float32), np.zeros(pad_count, dtype=np.float32)], axis=0)
        else:
            x = base
            mask = np.ones(window, dtype=np.float32)
        sequences.append(
            {
                "X": x.astype(np.float32),
                "valid_mask": mask.astype(np.float32),
                "label_id": int(label_id),
                "label_name": label_name,
                "video": video_name,
                "start_frame": 0,
                "end_frame": n - 1,
                "frames_source_path": source_path,
            }
        )
        return sequences

    for start in range(0, n - window + 1, step):
        end = start + window
        x = np.stack(frames[start:end], axis=0).astype(np.float32)
        mask = np.ones(window, dtype=np.float32)
        sequences.append(
            {
                "X": x,
                "valid_mask": mask,
                "label_id": int(label_id),
                "label_name": label_name,
                "video": video_name,
                "start_frame": start,
                "end_frame": end - 1,
                "frames_source_path": source_path,
            }
        )
    return sequences


def stratified_split(samples: list[dict[str, Any]], val_ratio: float, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in samples:
        by_label[int(s["label_id"])].append(s)

    rng = random.Random(seed)
    train: list[dict[str, Any]] = []
    val: list[dict[str, Any]] = []

    for _, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_val = int(round(n * val_ratio))
        if n > 1:
            n_val = min(max(n_val, 1), n - 1)
        else:
            n_val = 0
        val.extend(group[:n_val])
        train.extend(group[n_val:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


class SequenceDataset(Dataset):
    def __init__(self, samples: list[dict[str, Any]]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        s = self.samples[idx]
        x = torch.from_numpy(s["X"]).float()
        mask = torch.from_numpy(s["valid_mask"]).float()
        y = torch.tensor(int(s["label_id"]), dtype=torch.long)
        return x, mask, y


def masked_accuracy(logits: torch.Tensor, y: torch.Tensor) -> float:
    pred = torch.argmax(logits, dim=1)
    return float((pred == y).float().mean().item())


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    model.eval()
    loss_fn = nn.CrossEntropyLoss()
    losses: list[float] = []
    accs: list[float] = []
    with torch.no_grad():
        for x, mask, y in loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(x)
                loss = loss_fn(logits, y)
            losses.append(float(loss.item()))
            accs.append(masked_accuracy(logits, y))
    if not losses:
        return 0.0, 0.0
    return float(np.mean(losses)), float(np.mean(accs))


def update_live_plot(
    train_loss_hist: list[float],
    val_acc_hist: list[float],
    val_step_hist: list[int],
    lr_hist: list[float],
    out_plot: Path,
) -> None:
    plt.ioff()
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].plot(train_loss_hist, color="tab:blue")
    axes[0].set_title("Train Loss (per batch)")
    axes[0].set_xlabel("Batch")
    axes[0].set_ylabel("Loss")

    axes[1].plot(val_step_hist, val_acc_hist, color="tab:green", marker="o", markersize=3)
    axes[1].set_title("Val Accuracy (live eval)")
    axes[1].set_xlabel("Global batch")
    axes[1].set_ylabel("Accuracy")

    axes[2].plot(lr_hist, color="tab:orange")
    axes[2].set_title("LR Schedule (per batch)")
    axes[2].set_xlabel("Batch")
    axes[2].set_ylabel("LR")

    fig.tight_layout()
    fig.savefig(out_plot, dpi=140)
    plt.close(fig)


def build_lr_scheduler(
    optimizer: torch.optim.Optimizer,
    scheduler_name: str,
    total_steps: int,
    warmup_steps: int,
    base_lr: float,
    min_lr: float,
):
    if scheduler_name == "none":
        return None

    total_steps = max(total_steps, 1)
    warmup_steps = max(min(warmup_steps, total_steps - 1), 0)
    lr_span = max(base_lr - min_lr, 0.0)

    def lr_lambda(step: int) -> float:
        if step < warmup_steps and warmup_steps > 0:
            return float(step + 1) / float(warmup_steps)
        if lr_span <= 0.0:
            return 1.0
        progress = float(step - warmup_steps) / float(max(total_steps - warmup_steps, 1))
        progress = float(np.clip(progress, 0.0, 1.0))
        cosine = 0.5 * (1.0 + np.cos(np.pi * progress))
        lr = min_lr + lr_span * cosine
        return lr / max(base_lr, 1e-12)

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)


def main() -> int:
    args = parse_args()
    seed_everything(args.seed)

    if not torch.cuda.is_available():
        print("[train] FAIL: CUDA is required but unavailable")
        return 1

    device = torch.device("cuda")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.set_float32_matmul_precision("high")

    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = data_root / "manifest.json"
    videos_dir = data_root / "videos"
    if not manifest_path.exists():
        print(f"[train] FAIL: missing {manifest_path}")
        return 1
    if not videos_dir.exists():
        print(f"[train] FAIL: missing {videos_dir}")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    labels = manifest.get("labels", {})
    if not isinstance(labels, dict) or not labels:
        print("[train] FAIL: labels missing in manifest.json")
        return 1

    label_to_id: dict[str, int] = {str(k): int(v) for k, v in labels.items()}
    video_files = sorted(videos_dir.glob("*.jsonl"))
    if not video_files:
        print(f"[train] FAIL: no jsonl files in {videos_dir}")
        return 1

    all_samples: list[dict[str, Any]] = []
    for vf in video_files:
        label_name = infer_label_name_from_stem(vf.stem)
        if label_name not in label_to_id:
            print(f"[train] FAIL: label '{label_name}' missing in manifest labels")
            return 1
        label_id = label_to_id[label_name]

        try:
            frames = load_video_frames(vf)
        except Exception as exc:
            print(f"[train] FAIL transformed_missing_or_invalid in {vf}: {exc}")
            return 1

        seqs = build_padded_sequences(
            frames=frames,
            label_id=label_id,
            label_name=label_name,
            video_name=vf.stem,
            window=args.window,
            step=args.step,
            source_path=str(vf),
        )
        all_samples.extend(seqs)

    if not all_samples:
        print("[train] FAIL: no training samples built")
        return 1

    # strict class coverage
    class_counts = defaultdict(int)
    for s in all_samples:
        class_counts[int(s["label_id"])] += 1
    missing = [name for name, cid in label_to_id.items() if class_counts[int(cid)] == 0]
    if missing:
        print(f"[train] FAIL: missing classes after sequencing: {missing}")
        return 1

    train_samples, val_samples = stratified_split(all_samples, args.val_ratio, args.seed)
    if not train_samples or not val_samples:
        print("[train] FAIL: train/val split invalid")
        return 1

    # strict class coverage in both splits
    for split_name, split_samples in (("train", train_samples), ("val", val_samples)):
        split_counts = defaultdict(int)
        for s in split_samples:
            split_counts[int(s["label_id"])] += 1
        missing_split = [name for name, cid in label_to_id.items() if split_counts[int(cid)] == 0]
        if missing_split:
            print(f"[train] FAIL: split '{split_name}' missing classes: {missing_split}")
            return 1

    train_ds = SequenceDataset(train_samples)
    val_ds = SequenceDataset(val_samples)

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=True,
        drop_last=False,
        persistent_workers=args.num_workers > 0,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True,
        drop_last=False,
        persistent_workers=args.num_workers > 0,
    )

    cfg = ModelCfg(
        num_classes=len(label_to_id),
        d_model=256,
        n_heads=8,
        depth=8,
        dropout=args.dropout,
        mlp_ratio=4.0,
        max_spatial_dist=4,
        max_temporal_dist=min(64, args.window),
        root_joint=0,
    )
    model = GraphBiasedSTTransformer(num_joints=17, edges=[(int(a), int(b)) for a, b in RAW17_EDGES], cfg=cfg).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=float(args.label_smoothing))
    scaler = torch.amp.GradScaler("cuda")
    total_steps = args.epochs * max(len(train_loader), 1)
    warmup_steps = args.warmup_epochs * max(len(train_loader), 1)
    scheduler = build_lr_scheduler(
        optimizer=optimizer,
        scheduler_name=args.scheduler,
        total_steps=total_steps,
        warmup_steps=warmup_steps,
        base_lr=args.lr,
        min_lr=args.min_lr,
    )

    best_val_acc = -1.0
    best_val_loss = float("inf")
    global_batch = 0

    train_loss_hist: list[float] = []
    val_acc_hist: list[float] = []
    val_step_hist: list[int] = []
    lr_hist: list[float] = []

    out_plot = out_dir / "live_metrics.png"
    out_hist = out_dir / "live_metrics_history.json"
    out_best = out_dir / "best_model.pt"
    out_last = out_dir / "last_model.pt"

    print(
        f"[train] start cuda={torch.cuda.get_device_name(0)} "
        f"train={len(train_ds)} val={len(val_ds)} classes={label_to_id}"
    )

    for epoch in range(1, args.epochs + 1):
        model.train()
        for x, mask, y in train_loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(x)
                loss = loss_fn(logits, y)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
            if scheduler is not None:
                scheduler.step()

            batch_loss = float(loss.item())
            batch_acc = masked_accuracy(logits.detach(), y)
            train_loss_hist.append(batch_loss)
            global_batch += 1
            current_lr = float(optimizer.param_groups[0]["lr"])
            lr_hist.append(current_lr)

            gpu_mem_mb = torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0)
            print(
                f"[train][e{epoch:03d}][b{global_batch:05d}] "
                f"loss={batch_loss:.4f} acc={batch_acc:.4f} lr={current_lr:.6f} "
                f"gpu_mem_mb={gpu_mem_mb:.1f}"
            )

            if global_batch % max(args.eval_every_batches, 1) == 0:
                val_loss, val_acc = evaluate(model, val_loader, device)
                val_acc_hist.append(val_acc)
                val_step_hist.append(global_batch)
                print(
                    f"[eval][e{epoch:03d}][b{global_batch:05d}] "
                    f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
                )

                is_better = (val_acc > best_val_acc) or (np.isclose(val_acc, best_val_acc) and val_loss < best_val_loss)
                if is_better:
                    best_val_acc = val_acc
                    best_val_loss = val_loss
                    torch.save(
                        {
                            "model_state_dict": model.state_dict(),
                            "optimizer_state_dict": optimizer.state_dict(),
                            "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
                            "epoch": epoch,
                            "global_batch": global_batch,
                            "best_val_acc": best_val_acc,
                            "best_val_loss": best_val_loss,
                            "label_map": label_to_id,
                            "cfg": asdict(cfg),
                        },
                        out_best,
                    )
                    print(
                        f"[train] new best saved: {out_best} "
                        f"(val_acc={best_val_acc:.4f}, val_loss={best_val_loss:.4f})"
                    )

                update_live_plot(train_loss_hist, val_acc_hist, val_step_hist, lr_hist, out_plot)
                out_hist.write_text(
                    json.dumps(
                        {
                            "train_loss_per_batch": train_loss_hist,
                            "val_acc_per_eval": val_acc_hist,
                            "val_eval_steps": val_step_hist,
                            "lr_per_batch": lr_hist,
                            "best_val_acc": best_val_acc,
                            "best_val_loss": best_val_loss,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
                "epoch": epoch,
                "global_batch": global_batch,
                "best_val_acc": best_val_acc,
                "best_val_loss": best_val_loss,
                "label_map": label_to_id,
                "cfg": asdict(cfg),
            },
            out_last,
        )

        if epoch % max(args.save_every_epochs, 1) == 0:
            ckpt = out_dir / f"checkpoint_epoch_{epoch}.pt"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
                    "epoch": epoch,
                    "global_batch": global_batch,
                    "best_val_acc": best_val_acc,
                    "best_val_loss": best_val_loss,
                    "label_map": label_to_id,
                    "cfg": asdict(cfg),
                },
                ckpt,
            )
            print(f"[train] checkpoint saved: {ckpt}")

    # final eval summary
    val_loss, val_acc = evaluate(model, val_loader, device)
    print(
        f"[train] done val_loss={val_loss:.4f} val_acc={val_acc:.4f} "
        f"best_val_acc={best_val_acc:.4f} best_val_loss={best_val_loss:.4f}"
    )
    print(f"[train] best={out_best}")
    print(f"[train] last={out_last}")
    print(f"[train] plot={out_plot}")
    print(f"[train] hist={out_hist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
