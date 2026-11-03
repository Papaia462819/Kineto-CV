import numpy as np
import pytest

from src.quality import (BAD_BONES, BAD_TRUNK, JUMP, LOW_VISIBILITY, MISSING, OK, UPSIDE_DOWN, QualityChecker,
                         clean_sequence, clip_reference)


def body():
    """(image_kp, world_kp) pentru o persoană cu fața la cameră: stânga ei apare în dreapta imaginii."""
    image = np.full((33, 4), 0.5)
    world = np.zeros((33, 4))
    xy = {
        11: (0.56, 0.30), 12: (0.44, 0.30), 13: (0.60, 0.42), 14: (0.40, 0.42), 15: (0.62, 0.54), 16: (0.38, 0.54),
        17: (0.63, 0.56), 18: (0.37, 0.56), 19: (0.63, 0.57), 20: (0.37, 0.57), 21: (0.63, 0.55), 22: (0.37, 0.55),
        23: (0.54, 0.55), 24: (0.46, 0.55), 25: (0.54, 0.72), 26: (0.46, 0.72), 27: (0.54, 0.88), 28: (0.46, 0.88),
        29: (0.55, 0.90), 30: (0.45, 0.90), 31: (0.56, 0.91), 32: (0.44, 0.91),
    }
    for i, (x, y) in xy.items():
        image[i, :2] = x, y
        world[i, :3] = (x - 0.5) * 2, (y - 0.55) * 2, 0.0
    image[:, 3] = world[:, 3] = 0.99
    return image, world


def checker_ready(**options):
    checker = QualityChecker(**options)
    for _ in range(20):
        assert checker.update(*body())[2] == OK
    return checker


def test_good_frame_passes_unchanged():
    image, world = body()
    out_image, out_world, status = QualityChecker().update(image, world)
    assert status == OK
    assert np.array_equal(out_image, image)
    assert np.array_equal(out_world, world)


def test_input_is_not_modified():
    image, world = body()
    image[[11, 12]] = image[[12, 11]]
    before = image.copy()
    QualityChecker().update(image, world)
    assert np.array_equal(image, before)


def test_missing_frame():
    image, world = body()
    out_image, _, status = QualityChecker().update(image * np.nan, world * np.nan)
    assert status == MISSING
    assert np.isnan(out_image).all()


def test_swapped_arms_are_fixed_in_image_and_world():
    good_image, good_world = body()
    image, world = body()
    left, right = [11, 13, 15, 17, 19, 21], [12, 14, 16, 18, 20, 22]
    image[left + right] = image[right + left]
    world[left + right] = world[right + left]
    checker = QualityChecker()
    out_image, out_world, status = checker.update(image, world)
    assert status == OK
    assert checker.swaps == 1
    np.testing.assert_array_equal(out_image, good_image)
    np.testing.assert_array_equal(out_world, good_world)


def test_legs_can_be_swapped_independently_of_arms():
    good_image, _ = body()
    image, world = body()
    left, right = [23, 25, 27, 29, 31], [24, 26, 28, 30, 32]
    image[left + right] = image[right + left]
    world[left + right] = world[right + left]
    out_image, _, status = QualityChecker().update(image, world)
    assert status == OK
    np.testing.assert_array_equal(out_image, good_image)


def test_mirrored_view_expects_opposite_order():
    image, world = body()
    checker = QualityChecker(mirrored=True)
    out_image, _, _ = checker.update(image, world)
    assert out_image[11, 0] < out_image[12, 0]
    assert checker.swaps == 1


def test_sideways_camera_uses_previous_frame():
    checker = QualityChecker(facing_camera=False)
    good_image, good_world = body()
    checker.update(good_image, good_world)
    image, world = body()
    left, right = [11, 13, 15, 17, 19, 21], [12, 14, 16, 18, 20, 22]
    image[left + right] = image[right + left]
    world[left + right] = world[right + left]
    out_image, _, status = checker.update(image, world)
    assert status == OK
    assert checker.swaps == 1
    np.testing.assert_array_equal(out_image, good_image)


def test_sideways_camera_leaves_correct_frames_alone():
    checker = QualityChecker(facing_camera=False)
    for _ in range(3):
        checker.update(*body())
    assert checker.swaps == 0


def test_low_visibility_is_rejected():
    image, world = body()
    world[11, 3] = 0.1
    assert QualityChecker().update(image, world)[2] == LOW_VISIBILITY


def test_upside_down_body_is_rejected_unless_lying_is_allowed():
    image, world = body()
    image[[11, 12], 1] = 0.70
    assert QualityChecker().update(image, world)[2] == UPSIDE_DOWN
    assert QualityChecker(upright=False).update(image, world)[2] == OK


def test_upside_down_frames_do_not_spoil_clip_reference():
    frames = [body() for _ in range(10)]
    images, worlds = np.stack([f[0] for f in frames]), np.stack([f[1] for f in frames])
    expected = clip_reference(images, worlds)[1]
    images[:4, [11, 12], 1] = 0.75
    assert clip_reference(images, worlds)[1] == pytest.approx(expected)


def test_unequal_bones_are_rejected():
    image, world = body()
    world[13, :3] = world[11, :3] + (world[13, :3] - world[11, :3]) * 3
    assert QualityChecker().update(image, world)[2] == BAD_BONES


def test_both_bones_changing_is_caught_by_reference():
    checker = checker_ready()
    image, world = body()
    for shoulder, elbow in ((11, 13), (12, 14)):
        world[elbow, :3] = world[shoulder, :3] + (world[elbow, :3] - world[shoulder, :3]) * 3
    assert checker.update(image, world)[2] == BAD_BONES


def test_shrunken_trunk_is_rejected():
    checker = checker_ready(max_image_speed=1e9)
    image, world = body()
    image[[11, 12], 1] = 0.50
    assert checker.update(image, world)[2] == BAD_TRUNK


def test_sudden_jump_is_rejected_but_slow_motion_is_not():
    checker = checker_ready()
    image, world = body()
    image[15, 0] += 0.02
    assert checker.update(image, world)[2] == OK
    image, world = body()
    image[15, 0] += 0.3
    assert checker.update(image, world)[2] == JUMP


def test_jump_allowance_grows_with_missing_frames():
    checker = checker_ready()
    empty = np.full((33, 4), np.nan)
    for _ in range(10):
        checker.update(empty, empty)
    image, world = body()
    image[15, 0] += 0.3
    assert checker.update(image, world)[2] == OK


def test_live_checker_recovers_after_person_really_moves_closer():
    checker = checker_ready()
    image, world = body()
    image[:, :2] = 0.5 + (image[:, :2] - 0.5) * 1.3
    image[:, 1] = image[:, 1] + 0  # persoana rămâne în cadru
    image[[11, 12], 1] -= 0.25
    statuses = [checker.update(image, world)[2] for _ in range(40)]
    assert statuses[0] != OK
    assert statuses[-1] == OK


def test_clean_sequence_keeps_frame_count_and_rejects_bad_frame():
    frames = [body() for _ in range(40)]
    images, worlds = np.stack([f[0] for f in frames]), np.stack([f[1] for f in frames])
    images[20, [11, 12], 1] = 0.50
    out_i, out_w, status, swaps = clean_sequence(images, worlds)
    assert out_i.shape == images.shape
    assert status[20] != OK
    assert np.isnan(out_w[20]).all()
    assert (status == OK).sum() == 39
    assert swaps == 0


def test_clip_reference_ignores_missing_frames_and_handles_empty_clip():
    frames = [body() for _ in range(5)]
    images, worlds = np.stack([f[0] for f in frames]), np.stack([f[1] for f in frames])
    images[1] = worlds[1] = np.nan
    bones, trunk = clip_reference(images, worlds)
    assert trunk == pytest.approx(0.25)
    assert bones.shape == (8,)
    assert clip_reference(images * np.nan, worlds * np.nan) is None
