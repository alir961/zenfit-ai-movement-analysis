from labs.estimation.kalman_bank import KalmanBank3D


def test_kalman_predict_update_cycle():
    bank = KalmanBank3D()
    p0 = bank.update_joint("nose", (10.0, 20.0, 0.0), 0.9, 1.0 / 30.0)
    assert abs(p0[0] - 10.0) < 1e-3

    bank.update_joint("nose", (11.0, 20.0, 0.0), 0.9, 1.0 / 30.0)
    pred = bank.predict_all(1.0 / 30.0)["nose"]
    assert pred[0] > 10.5
