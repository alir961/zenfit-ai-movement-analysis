from labs.runtime.scheduler import AdaptiveState, FrameScheduler


def test_fixed_scheduler_skip3():
    sched = FrameScheduler(mode="fixed", skip_fixed=3)
    infer_indices = [i for i in range(12) if sched.should_infer(i, AdaptiveState())]
    assert infer_indices == [0, 4, 8]


def test_adaptive_scheduler_bounds():
    sched = FrameScheduler(mode="adaptive", skip_fixed=3, max_skip=5)
    state = AdaptiveState(motion_score=0.2, confidence_score=0.8, infer_ms=20.0)
    skip = sched.infer_interval(10, state)
    assert 0 <= skip <= 5
