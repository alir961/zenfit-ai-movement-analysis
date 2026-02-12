from __future__ import annotations

import queue
from multiprocessing import Queue
from typing import Dict, Iterable, List, Tuple

import numpy as np


def _bgr_to_rgb01(color_bgr: Tuple[int, int, int]) -> Tuple[float, float, float]:
    b, g, r = color_bgr
    return (float(r) / 255.0, float(g) / 255.0, float(b) / 255.0)


def run_pyplot_process(
    data_queue: Queue,
    skeleton_links: Iterable[Tuple[str, str]],
    core_names: Iterable[str] | None = None,
    keypoint_colors: Dict[str, Tuple[int, int, int]] | None = None,
    link_colors: Dict[Tuple[str, str], Tuple[int, int, int]] | None = None,
    interval_ms: int = 33,
    plot_space: str = "canonical",
    draw_min_conf: float = 0.10,
    show_noncore_points: bool = True,
) -> None:
    import matplotlib
    try:
        matplotlib.use("TkAgg")
    except Exception:
        pass
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    links = list(skeleton_links)
    core_name_set = set(core_names or [])
    kp_colors = dict(keypoint_colors or {})
    lk_colors = dict(link_colors or {})
    mode = plot_space if plot_space in ("raw", "canonical", "both") else "canonical"
    conf_thr = max(0.0, min(1.0, float(draw_min_conf)))
    soft_conf = max(0.01, min(0.08, conf_thr * 0.5))
    draw_noncore = bool(show_noncore_points)

    latest = {
        "frame_idx": -1,
        "source": "none",
        "quality": 0.0,
        "flags": [],
        "raw_joints": [],
        "canonical_joints": [],
        "measurement_age_frames": -1,
        "queue_delay_ms": 0.0,
        "canonical_yaw_deg": 0.0,
        "axis_span": 1.4,
    }

    fig = plt.figure(figsize=(7.2, 7.2))
    ax = fig.add_subplot(111, projection="3d")
    if getattr(fig.canvas, "manager", None) is not None:
        fig.canvas.manager.set_window_title("ZenFit Labs 3D")

    scatter = ax.scatter([], [], [], s=16, c=[])
    ghost = ax.scatter([], [], [], s=11, c="#9a9a9a", alpha=0.25)
    line_artists = [ax.plot([], [], [], color="#c0c0c0", linewidth=1.8)[0] for _ in links]
    info_txt = ax.text2D(0.02, 0.96, "", transform=ax.transAxes)

    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_zlim(-1.5, 1.5)
    ax.set_xlabel("X lateral")
    ax.set_ylabel("Y up")
    ax.set_zlabel("Z depth")
    ax.view_init(elev=18, azim=58)

    def _drain_queue() -> bool:
        while True:
            try:
                msg = data_queue.get_nowait()
            except queue.Empty:
                return True
            if not isinstance(msg, dict):
                continue
            typ = msg.get("type")
            if typ == "stop":
                plt.close(fig)
                return False
            if typ == "state":
                latest.update(msg.get("payload", {}))

    def _named_map(joints: List[dict]) -> Dict[str, dict]:
        return {str(j.get("name", "")): j for j in joints}

    def _joint_color(name: str):
        if name in kp_colors:
            return _bgr_to_rgb01(kp_colors[name])
        lname = name.lower()
        if "left" in lname:
            return "#4caf50"
        if "right" in lname:
            return "#ff5252"
        if any(k in lname for k in ("nose", "eye", "ear", "face", "head")):
            return "#f4d03f"
        return "#42a5f5"

    def _link_color(a: str, b: str):
        if (a, b) in lk_colors:
            return _bgr_to_rgb01(lk_colors[(a, b)])
        if (b, a) in lk_colors:
            return _bgr_to_rgb01(lk_colors[(b, a)])
        return "#c0c0c0"

    def _select_joints() -> tuple[List[dict], List[dict]]:
        raw = list(latest.get("raw_joints", []) or [])
        fused = list(latest.get("fused_body17_joints", []) or [])
        canonical = list(latest.get("canonical_joints", []) or [])
        if not canonical and fused:
            canonical = fused
        if mode == "raw":
            return raw, []
        if mode == "both":
            return canonical if canonical else raw, raw if canonical else []
        return canonical if canonical else raw, []

    def update(_):
        ok = _drain_queue()
        if not ok:
            return [scatter, ghost, info_txt, *line_artists]

        active, aux = _select_joints()
        if not active:
            info_txt.set_text("waiting for pose...")
            return [scatter, ghost, info_txt, *line_artists]

        named = _named_map(active)
        visible = [j for j in active if float(j.get("c", 0.0)) >= soft_conf]
        if not visible:
            info_txt.set_text("waiting for confident joints...")
            return [scatter, ghost, info_txt, *line_artists]

        xs, ys, zs, colors = [], [], [], []
        for j in visible:
            name = str(j.get("name", ""))
            is_core = (not core_name_set) or (name in core_name_set)
            if (not is_core) and (not draw_noncore):
                continue
            x = float(j.get("x", 0.0))
            y = float(j.get("y", 0.0))
            z = float(j.get("z", 0.0))
            c = float(j.get("c", 0.0))
            xs.append(x)
            ys.append(y)
            zs.append(z)
            col = _joint_color(name)
            if c < conf_thr:
                if isinstance(col, tuple):
                    col = (0.35 * col[0], 0.35 * col[1], 0.35 * col[2])
                colors.append(col)
            else:
                colors.append(col)

        if not xs:
            info_txt.set_text("waiting for filtered joints...")
            return [scatter, ghost, info_txt, *line_artists]

        robust_vals = []
        for j in visible:
            if float(j.get("c", 0.0)) >= conf_thr:
                robust_vals.extend(
                    [
                        abs(float(j.get("x", 0.0))),
                        abs(float(j.get("y", 0.0))),
                        abs(float(j.get("z", 0.0))),
                    ]
                )
        if not robust_vals:
            robust_vals = [abs(v) for v in xs + ys + zs]
        robust = float(np.percentile(np.asarray(robust_vals, dtype=np.float64), 95)) if robust_vals else 1.0
        max_abs = max(1.0, robust)
        latest["axis_span"] = 0.90 * float(latest.get("axis_span", 1.4)) + 0.10 * max_abs
        span = max(1.2, min(4.5, float(latest["axis_span"]) * 1.35))
        ax.set_xlim(-span, span)
        ax.set_ylim(-span, span)
        ax.set_zlim(-span, span)

        scatter._offsets3d = (xs, ys, zs)
        scatter.set_color(colors)

        if aux:
            gx = [float(j.get("x", 0.0)) for j in aux if float(j.get("c", 0.0)) >= soft_conf]
            gy = [float(j.get("y", 0.0)) for j in aux if float(j.get("c", 0.0)) >= soft_conf]
            gz = [float(j.get("z", 0.0)) for j in aux if float(j.get("c", 0.0)) >= soft_conf]
            ghost._offsets3d = (gx, gy, gz)
        else:
            ghost._offsets3d = ([], [], [])

        for i, (a, b) in enumerate(links):
            ja = named.get(a)
            jb = named.get(b)
            if not ja or not jb:
                line_artists[i].set_data_3d([], [], [])
                continue
            conf = min(float(ja.get("c", 0.0)), float(jb.get("c", 0.0)))
            if conf < soft_conf:
                line_artists[i].set_data_3d([], [], [])
                continue
            line_artists[i].set_data_3d(
                [float(ja.get("x", 0.0)), float(jb.get("x", 0.0))],
                [float(ja.get("y", 0.0)), float(jb.get("y", 0.0))],
                [float(ja.get("z", 0.0)), float(jb.get("z", 0.0))],
            )
            line_artists[i].set_color(_link_color(a, b))
            line_artists[i].set_alpha(1.0 if conf >= conf_thr else 0.35)
            line_artists[i].set_linewidth(1.8 if conf >= conf_thr else 1.0)

        flags = latest.get("flags", []) or []
        info_txt.set_text(
            "frame={frame} source={source} q={q:.2f} age={age} "
            "queue={queue:.1f}ms yaw={yaw:.1f}deg flags={flags}".format(
                frame=int(latest.get("frame_idx", -1)),
                source=str(latest.get("source", "none")),
                q=float(latest.get("quality", 0.0)),
                age=int(latest.get("measurement_age_frames", -1)),
                queue=float(latest.get("queue_delay_ms", 0.0)),
                yaw=float(latest.get("canonical_yaw_deg", 0.0)),
                flags=",".join(flags[:2]) if flags else "none",
            )
        )
        return [scatter, ghost, info_txt, *line_artists]

    anim = FuncAnimation(
        fig,
        update,
        interval=max(15, int(interval_ms)),
        blit=False,
        cache_frame_data=False,
    )
    fig._anim_ref = anim
    plt.show()
