from labs.rig_profile import get_rig_profile


def test_coco133_profile_is_available():
    profile = get_rig_profile("coco133")
    assert profile.name == "coco133"
    assert len(profile.keypoint_names) >= 17
    assert len(profile.skeleton_links) >= 16
    assert "left_hip" in profile.keypoint_names
    assert "right_hip" in profile.keypoint_names


def test_body17_profile_is_subset():
    profile = get_rig_profile("body17")
    assert profile.name == "body17"
    assert len(profile.keypoint_names) == 17
    assert ("left_shoulder", "left_elbow") in profile.skeleton_links
