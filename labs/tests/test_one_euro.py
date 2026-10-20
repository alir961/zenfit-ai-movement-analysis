import numpy as np

from labs.estimation.one_euro import OneEuroFilter


def test_one_euro_reduces_noise_variance():
    rng = np.random.default_rng(0)
    base = np.sin(np.linspace(0, 4.0, 200))
    noisy = base + rng.normal(0.0, 0.12, size=base.shape)

    f = OneEuroFilter(min_cutoff=1.0, beta=0.02)
    out = np.array([f.update(float(x), 1.0 / 30.0) for x in noisy])

    assert np.var(out - base) < np.var(noisy - base)
