import random

from app.processing.smoothing import PoseSmoother


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _frame(x, c=0.9):
    return {"t": 0.0, "space": "normalized", "joints": [{"name": "left_knee", "x": x, "y": 0.0, "z": 0.0, "c": c}]}


def _x(frame):
    return frame["joints"][0]["x"]


def test_reduces_jitter_on_a_still_joint():
    rng = random.Random(0)
    clock = FakeClock()
    smoother = PoseSmoother(clock=clock)
    raw, smoothed = [], []
    for _ in range(100):
        clock.t += 0.1
        x = rng.gauss(0.0, 0.05)
        raw.append(x)
        smoothed.append(_x(smoother.update(_frame(x))))

    def var(values):
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)

    assert var(smoothed[10:]) < var(raw[10:]) / 2


def test_follows_a_large_move():
    clock = FakeClock()
    smoother = PoseSmoother(clock=clock)
    for _ in range(5):
        clock.t += 0.1
        smoother.update(_frame(0.0))
    for _ in range(5):
        clock.t += 0.1
        out = _x(smoother.update(_frame(1.0)))
    assert out > 0.9


def test_low_confidence_joint_is_passed_through():
    clock = FakeClock()
    smoother = PoseSmoother(clock=clock)
    clock.t += 0.1
    smoother.update(_frame(0.0))
    clock.t += 0.1
    assert _x(smoother.update(_frame(5.0, c=0.1))) == 5.0


def test_restarts_after_a_gap():
    clock = FakeClock()
    smoother = PoseSmoother(clock=clock)
    clock.t += 0.1
    smoother.update(_frame(0.0))
    clock.t += 2.0
    assert _x(smoother.update(_frame(3.0))) == 3.0
