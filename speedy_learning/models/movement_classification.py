# (B, S, J, 7)
# (Batch, sequences, joints, 3 vector (position) + 4 (rotations) quaternions)
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


# ----------------------------
# Quaternion utilities
# ----------------------------
def quat_normalize(q: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    # q: (..., 4)
    return q / (q.norm(dim=-1, keepdim=True).clamp_min(eps))

def quat_canonicalize_w_positive(q: torch.Tensor) -> torch.Tensor:
    # Enforce w >= 0 to remove q <-> -q ambiguity.
    # q: (...,4) where q[...,0] is w (assumed wxyz here)
    sign = torch.where(q[..., 0:1] < 0, -torch.ones_like(q[..., 0:1]), torch.ones_like(q[..., 0:1]))
    return q * sign


# ----------------------------
# Graph utilities (distance bias)
# ----------------------------
def build_shortest_path_dist(num_nodes: int, edges: List[Tuple[int, int]]) -> torch.Tensor:
    """
    Returns dist matrix (J,J) with shortest path lengths, clipped later.
    Floyd-Warshall on CPU (J is small, ~17-25-50).
    """
    dist = torch.full((num_nodes, num_nodes), fill_value=10_000, dtype=torch.long)
    dist.fill_diagonal_(0)
    for a, b in edges:
        dist[a, b] = 1
        dist[b, a] = 1
    # Floyd-Warshall
    for k in range(num_nodes):
        dist = torch.minimum(dist, dist[:, k:k+1] + dist[k:k+1, :])
    return dist


# ----------------------------
# GPU-efficient multihead attention with SDPA
# ----------------------------
class SDPA_MHA(nn.Module):
    """
    Multi-Head Attention using torch.scaled_dot_product_attention (fast on GPU).
    Supports additive bias mask broadcastable to (B, H, Lq, Lk).
    """
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.0):
        super().__init__()
        assert d_model % n_heads == 0
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.dropout = dropout

        self.qkv = nn.Linear(d_model, 3 * d_model, bias=True)
        self.proj = nn.Linear(d_model, d_model, bias=True)

    def forward(self, x: torch.Tensor, attn_bias: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        x: (B, L, D)
        attn_bias: float tensor broadcastable to (B, H, L, L) (additive to attention logits)
        """
        B, L, D = x.shape
        qkv = self.qkv(x)  # (B, L, 3D)
        q, k, v = qkv.chunk(3, dim=-1)

        # (B, H, L, d_head)
        q = q.view(B, L, self.n_heads, self.d_head).transpose(1, 2)
        k = k.view(B, L, self.n_heads, self.d_head).transpose(1, 2)
        v = v.view(B, L, self.n_heads, self.d_head).transpose(1, 2)

        # SDPA handles flash attention when available
        # attn_mask supports float additive masks
        out = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask=attn_bias,
            dropout_p=self.dropout if self.training else 0.0,
            is_causal=False,
        )  # (B, H, L, d_head)

        out = out.transpose(1, 2).contiguous().view(B, L, D)
        return self.proj(out)


class MLP(nn.Module):
    def __init__(self, d_model: int, mlp_ratio: float = 4.0, dropout: float = 0.0):
        super().__init__()
        hidden = int(d_model * mlp_ratio)
        self.fc1 = nn.Linear(d_model, hidden)
        self.fc2 = nn.Linear(hidden, d_model)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = F.gelu(x)
        x = self.drop(x)
        x = self.fc2(x)
        x = self.drop(x)
        return x


# ----------------------------
# Factorized Spatio-Temporal Block (Spatial MHA + Temporal MHA)
# ----------------------------
class STBlock(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.0, mlp_ratio: float = 4.0):
        super().__init__()
        self.norm_s = nn.LayerNorm(d_model)
        self.norm_t = nn.LayerNorm(d_model)
        self.norm_mlp = nn.LayerNorm(d_model)

        self.s_attn = SDPA_MHA(d_model, n_heads, dropout=dropout)
        self.t_attn = SDPA_MHA(d_model, n_heads, dropout=dropout)

        self.mlp = MLP(d_model, mlp_ratio=mlp_ratio, dropout=dropout)

    def forward(
        self,
        x: torch.Tensor,                 # (B, T, J, D)
        spatial_bias: Optional[torch.Tensor] = None,  # (1 or B*T, H, J, J)
        temporal_bias: Optional[torch.Tensor] = None, # (1 or B*J, H, T, T)
    ) -> torch.Tensor:
        B, T, J, D = x.shape

        # ---- Spatial attention: per time step, attend over joints
        xs = self.norm_s(x).reshape(B * T, J, D)  # (B*T, J, D)
        xs = self.s_attn(xs, attn_bias=spatial_bias)  # (B*T, J, D)
        x = x + xs.reshape(B, T, J, D)

        # ---- Temporal attention: per joint, attend over time
        xt = self.norm_t(x).transpose(1, 2).reshape(B * J, T, D)  # (B*J, T, D)
        xt = self.t_attn(xt, attn_bias=temporal_bias)  # (B*J, T, D)
        x = x + xt.reshape(B, J, T, D).transpose(1, 2)

        # ---- MLP
        xm = self.mlp(self.norm_mlp(x))
        x = x + xm
        return x


# ----------------------------
# Attention pooling for classification
# ----------------------------
class AttnPool(nn.Module):
    """
    Learnable token pooling: weights each (t,j) token.
    """
    def __init__(self, d_model: int, dropout: float = 0.0):
        super().__init__()
        self.score = nn.Linear(d_model, 1)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, J, D)
        B, T, J, D = x.shape
        tokens = x.reshape(B, T * J, D)
        logits = self.score(self.drop(tokens)).squeeze(-1)  # (B, TJ)
        w = F.softmax(logits, dim=-1).unsqueeze(-1)         # (B, TJ, 1)
        return (tokens * w).sum(dim=1)                      # (B, D)


# ----------------------------
# Main model
# ----------------------------
@dataclass
class ModelCfg:
    num_classes: int = 4
    d_model: int = 256
    n_heads: int = 8
    depth: int = 8
    dropout: float = 0.1
    mlp_ratio: float = 4.0
    max_spatial_dist: int = 4     # clip graph distances
    max_temporal_dist: int = 32   # clip temporal rel distances
    root_joint: int = 0           # change according to your skeleton


class GraphBiasedSTTransformer(nn.Module):
    """
    Input: (B, T, J, 7) where 7 = xyz + quat(wxyz)
    Internally adds velocity (xyz diff), so feature dim becomes 10.
    """
    def __init__(self, num_joints: int, edges: List[Tuple[int, int]], cfg: ModelCfg):
        super().__init__()
        self.J = num_joints
        self.cfg = cfg

        # Precompute skeleton shortest-path distances (J,J)
        dist = build_shortest_path_dist(num_joints, edges)  # CPU long
        dist = dist.clamp_max(cfg.max_spatial_dist)         # clip
        self.register_buffer("sp_dist", dist, persistent=False)

        # Spatial bias embedding: (dist -> per-head bias)
        # shape: (max_dist+1, n_heads)
        self.s_bias = nn.Embedding(cfg.max_spatial_dist + 1, cfg.n_heads)

        # Temporal relative bias (|dt| -> per-head bias)
        self.t_bias = nn.Embedding(cfg.max_temporal_dist + 1, cfg.n_heads)

        # Feature embed: xyz + dxyz + quat = 3 + 3 + 4 = 10
        self.in_dim = 10
        self.feat = nn.Linear(self.in_dim, cfg.d_model)

        # Joint ID embedding (gives identity to each joint token)
        self.joint_emb = nn.Embedding(num_joints, cfg.d_model)

        self.drop = nn.Dropout(cfg.dropout)

        self.blocks = nn.ModuleList([
            STBlock(cfg.d_model, cfg.n_heads, dropout=cfg.dropout, mlp_ratio=cfg.mlp_ratio)
            for _ in range(cfg.depth)
        ])

        self.pool = AttnPool(cfg.d_model, dropout=cfg.dropout)
        self.head = nn.Sequential(
            nn.LayerNorm(cfg.d_model),
            nn.Linear(cfg.d_model, cfg.num_classes)
        )

    def _make_spatial_bias(self, B: int, T: int, device: torch.device) -> torch.Tensor:
        """
        Returns bias shaped (B*T, H, J, J) as float.
        """
        # dist: (J,J) long -> embed -> (J,J,H) -> permute -> (1,H,J,J)
        dist = self.sp_dist.to(device=device)
        bias = self.s_bias(dist)              # (J,J,H)
        bias = bias.permute(2, 0, 1).unsqueeze(0)  # (1,H,J,J)
        # Broadcast over batch*time by expand + reshape
        bias = bias.expand(B * T, -1, -1, -1).contiguous()
        return bias

    def _make_temporal_bias(self, B: int, T: int, device: torch.device) -> torch.Tensor:
        """
        Returns bias shaped (B*J, H, T, T) as float, based on clipped |dt|.
        """
        # Build |i-j| matrix once per forward (T varies)
        idx = torch.arange(T, device=device)
        rel = (idx[None, :] - idx[:, None]).abs().clamp_max(self.cfg.max_temporal_dist)  # (T,T)
        bias = self.t_bias(rel)  # (T,T,H)
        bias = bias.permute(2, 0, 1).unsqueeze(0)  # (1,H,T,T)
        bias = bias.expand(B * self.J, -1, -1, -1).contiguous()
        return bias

    def _normalize_positions(self, p: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
        """
        p: (B,T,J,3)
        - center around root joint
        - scale by RMS
        """
        root = p[:, :, self.cfg.root_joint:self.cfg.root_joint+1, :]  # (B,T,1,3)
        p = p - root
        # RMS over (T,J,3)
        scale = torch.sqrt((p ** 2).mean(dim=(1, 2, 3), keepdim=True).clamp_min(eps))
        p = p / scale
        return p

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, T, J, 7) = xyz + quat(wxyz)
        returns logits: (B, num_classes)
        """
        assert x.ndim == 4 and x.shape[-1] == 7 and x.shape[2] == self.J
        B, T, J, _ = x.shape
        device = x.device

        pos = x[..., 0:3]
        quat = x[..., 3:7]

        # Normalize positions
        pos = self._normalize_positions(pos)

        # Normalize + canonicalize quaternion
        quat = quat_normalize(quat)
        quat = quat_canonicalize_w_positive(quat)

        # Velocity feature (pos diff)
        vel = torch.zeros_like(pos)
        vel[:, 1:, :, :] = pos[:, 1:, :, :] - pos[:, :-1, :, :]

        feats = torch.cat([pos, vel, quat], dim=-1)  # (B,T,J,10)

        # Embed
        h = self.feat(feats)  # (B,T,J,D)

        # Add joint id embedding
        joint_ids = torch.arange(J, device=device)
        h = h + self.joint_emb(joint_ids)[None, None, :, :]  # broadcast to (B,T,J,D)
        h = self.drop(h)

        # Build biases (additive to attention logits)
        s_bias = self._make_spatial_bias(B, T, device=device)  # (B*T,H,J,J)
        t_bias = self._make_temporal_bias(B, T, device=device) # (B*J,H,T,T)

        for blk in self.blocks:
            h = blk(h, spatial_bias=s_bias, temporal_bias=t_bias)

        pooled = self.pool(h)          # (B,D)
        logits = self.head(pooled)     # (B,C)
        return logits


# ----------------------------
# Example edges (COCO-17-ish)
# Adjust to YOUR skeleton format.
# ----------------------------
def coco17_edges() -> List[Tuple[int, int]]:
    # This is a common COCO-like kinematic tree (may differ in your dataset).
    # Indices are dataset-dependent: adjust carefully.
    return [
        (0, 1), (1, 2), (2, 3), (3, 4),      # right arm chain (example)
        (0, 5), (5, 6), (6, 7), (7, 8),      # left arm chain
        (0, 9), (9, 10), (10, 11),           # spine/head
        (9, 12), (12, 13), (13, 14),         # right leg
        (9, 15), (15, 16),                   # left leg (example)
    ]


# ----------------------------
# Quick usage
# ----------------------------
if __name__ == "__main__":
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.set_float32_matmul_precision("high")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    B, T, J = 8, 120, 17
    x = torch.randn(B, T, J, 7, device=device)

    cfg = ModelCfg(num_classes=4, d_model=256, n_heads=8, depth=8, dropout=0.1, root_joint=0)
    model = GraphBiasedSTTransformer(num_joints=J, edges=coco17_edges(), cfg=cfg).to(device)

    # Optional: compile for speed (PyTorch 2.x)
    # model = torch.compile(model)

    with torch.no_grad():
        y = model(x)
        print(y.shape)  # (B, 4)
