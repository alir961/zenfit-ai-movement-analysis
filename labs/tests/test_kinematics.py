import numpy as np

from labs.estimation.kinematics import quat_from_two_vectors, slerp


def test_quaternion_ops_are_normalized():
    q = quat_from_two_vectors(np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    assert abs(np.linalg.norm(q) - 1.0) < 1e-6

    qi = np.array([1.0, 0.0, 0.0, 0.0])
    qm = slerp(qi, q, 0.5)
    assert abs(np.linalg.norm(qm) - 1.0) < 1e-6
