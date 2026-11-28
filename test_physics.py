"""Automated checks for the flight physics in physics.py. Run them with: pytest"""

import math

import pytest

from physics import (
    DT, GRAVITY, DRY_MASS, START_FUEL, MAX_THRUST, MAX_FUEL_FLOW,
    MAX_GIMBAL, GIMBAL_RATE, LEG_STIFFNESS, SETTLE_TIME, Rocket,
)


def still_rocket():
    """A fresh rocket at the usual height, but centered with no sideways drift."""
    rocket = Rocket()
    rocket.x = 0.0
    rocket.vx = 0.0
    return rocket


def placed_rocket(height, x=0.0, vx=0.0, angle_degrees=0.0):
    """A rocket whose lowest point is `height` m above the ground, not moving down yet."""
    rocket = still_rocket()
    rocket.x = x
    rocket.vx = vx
    rocket.angle = math.radians(angle_degrees)
    rocket.y = rocket.y - (rocket.clearance() - height)
    return rocket


def fly(rocket, throttle, gimbal_command, seconds):
    """Hold the same controls for a number of seconds (or until the flight ends)."""
    for _ in range(round(seconds / DT)):
        if rocket.status != "flying":
            break
        rocket.step(throttle, gimbal_command)
    return rocket


# --- Gravity ------------------------------------------------------------------

def test_free_fall_time_matches_the_exact_formula():
    rocket = still_rocket()
    drop = rocket.clearance()          # How far the lowest point (the feet) has to fall.
    fly(rocket, 0.0, 0.0, seconds=10)
    # Exact physics: t = sqrt(2h / g). Our 1/60 s steps land within one step of it.
    assert rocket.time == pytest.approx(math.sqrt(2 * drop / GRAVITY), abs=DT)


def test_free_fall_impact_speed_matches_the_exact_formula():
    rocket = still_rocket()
    drop = rocket.clearance()
    fly(rocket, 0.0, 0.0, seconds=10)
    # Exact physics: v = sqrt(2gh).
    assert rocket.impact_speed == pytest.approx(math.sqrt(2 * GRAVITY * drop), abs=0.2)


def test_one_step_of_free_fall_adds_gravity_times_dt_to_the_fall_speed():
    rocket = still_rocket()
    rocket.step(0.0, 0.0)
    assert rocket.vy == pytest.approx(-GRAVITY * DT)


# --- Thrust -------------------------------------------------------------------

def test_hover_throttle_on_a_full_tank_holds_the_rocket_still():
    rocket = still_rocket()
    hover = (DRY_MASS + START_FUEL) * GRAVITY / MAX_THRUST
    assert hover == pytest.approx(0.49, abs=0.01)
    fly(rocket, hover, 0.0, seconds=1)
    # Burning fuel makes it slightly lighter, so it drifts up a tiny bit, but barely moves.
    assert abs(rocket.vy) < 0.1


def test_full_throttle_makes_the_rocket_climb():
    rocket = fly(still_rocket(), 1.0, 0.0, seconds=1)
    assert rocket.vy > 0


# --- Fuel ---------------------------------------------------------------------

def test_full_throttle_burns_1_375_kg_per_second():
    rocket = fly(still_rocket(), 1.0, 0.0, seconds=1)
    assert rocket.fuel == pytest.approx(START_FUEL - MAX_FUEL_FLOW)


def test_a_lighter_rocket_climbs_on_the_full_tank_hover_throttle():
    hover_when_full = (DRY_MASS + START_FUEL) * GRAVITY / MAX_THRUST
    rocket = still_rocket()
    rocket.fuel = START_FUEL / 2       # Half the fuel burned: 15 kg lighter.
    fly(rocket, hover_when_full, 0.0, seconds=1)
    # Same push, less mass: a = F / m - g is about +1.5 m/s², so after 1 s it climbs.
    assert rocket.vy > 1.0


def test_engine_off_burns_no_fuel():
    rocket = fly(still_rocket(), 0.0, 0.0, seconds=1)
    assert rocket.fuel == START_FUEL


def test_empty_tank_gives_no_thrust():
    rocket = still_rocket()
    rocket.fuel = 0.0
    rocket.step(1.0, 0.0)              # Full throttle, but nothing to burn.
    assert rocket.vy == pytest.approx(-GRAVITY * DT)


# --- Gimbal (the nozzle) ------------------------------------------------------

def test_nozzle_moves_at_most_gimbal_rate_per_step():
    rocket = still_rocket()
    rocket.step(0.5, 1.0)              # Ask for full right.
    assert rocket.gimbal == pytest.approx(GIMBAL_RATE * DT)    # 0.5 degrees, not 12.


def test_nozzle_stops_at_its_limit():
    rocket = fly(still_rocket(), 0.5, 1.0, seconds=2)          # Long enough to reach it.
    assert rocket.gimbal == pytest.approx(MAX_GIMBAL)


def test_out_of_range_controls_are_clamped():
    rocket = still_rocket()
    rocket.step(5.0, -9.0)
    assert rocket.throttle == 1.0
    assert rocket.gimbal == pytest.approx(-GIMBAL_RATE * DT)   # One normal step left.


# --- Steering -----------------------------------------------------------------

def test_nozzle_right_turns_the_nose_right():
    rocket = fly(still_rocket(), 0.5, 1.0, seconds=0.25)
    assert rocket.spin > 0             # Positive spin = clockwise = nose to the right.
    assert rocket.angle > 0


def test_steering_left_is_the_mirror_image_of_steering_right():
    right = fly(still_rocket(), 0.5, 1.0, seconds=1)
    left = fly(still_rocket(), 0.5, -1.0, seconds=1)
    assert left.angle == pytest.approx(-right.angle)
    assert left.x == pytest.approx(-right.x)
    assert left.y == pytest.approx(right.y)


def test_engine_off_means_no_steering():
    rocket = fly(still_rocket(), 0.0, 1.0, seconds=0.5)
    assert rocket.gimbal > 0           # The nozzle still swivels...
    assert rocket.spin == 0.0          # ...but with no thrust there is no torque.


# --- Legs ---------------------------------------------------------------------

def test_upright_feet_are_symmetric_and_below_the_body():
    rocket = still_rocket()
    (left_x, left_y), (right_x, right_y) = rocket.feet()
    assert left_x == pytest.approx(-right_x)               # Mirror images around x = 0.
    assert left_y == pytest.approx(right_y)                # Same height when upright.
    lowest_corner = min(y for _, y in rocket.corners())
    assert left_y < lowest_corner                          # The feet touch the ground first.
    assert rocket.clearance() == pytest.approx(left_y)


def test_tilting_right_swings_the_stance_to_the_left():
    rocket = still_rocket()
    rocket.angle = math.radians(10)                        # Nose leans right...
    assert rocket.stance_center()[0] < 0                   # ...so the feet swing left.
    assert rocket.pad_offset() == pytest.approx(rocket.stance_center()[0])


# --- Suspension and landing ---------------------------------------------------

def test_a_gentle_drop_on_the_pad_settles_and_lands():
    rocket = fly(placed_rocket(0.3), 0.0, 0.0, seconds=10)
    assert rocket.status == "landed"


def test_landing_waits_for_a_calm_moment_on_both_feet():
    rocket = placed_rocket(0.3)
    both_down_at = None
    for _ in range(round(10 / DT)):        # At most 10 s, so a rocket that never settles
        if rocket.status != "flying":      # fails this test instead of hanging it forever.
            break
        rocket.step(0.0, 0.0)
        if both_down_at is None and all(rocket.foot_contacts):
            both_down_at = rocket.time
    assert rocket.status == "landed"
    # Not landed the instant the feet touch, but only after SETTLE_TIME of calm.
    assert rocket.time - both_down_at >= SETTLE_TIME - DT


def test_the_legs_hold_the_weight_with_a_small_compression():
    rocket = fly(placed_rocket(0.3), 0.0, 0.0, seconds=10)
    weight = (DRY_MASS + rocket.fuel) * GRAVITY
    compression = -rocket.feet()[0][1]          # How far a foot is pressed into the ground.
    # At rest each spring carries half the weight: k x compression = weight / 2.
    assert compression == pytest.approx(weight / 2 / LEG_STIFFNESS, abs=0.02)


def test_a_hard_touchdown_breaks_a_leg():
    rocket = fly(placed_rocket(3.0), 0.0, 0.0, seconds=10)     # Hits at about 7.7 m/s.
    assert rocket.status == "crashed"
    assert "leg" in rocket.crash_reason


def test_a_slightly_tilted_touchdown_rocks_onto_both_feet():
    rocket = fly(placed_rocket(0.3, angle_degrees=8), 0.0, 0.0, seconds=10)
    assert rocket.status == "landed"
    assert abs(rocket.tilt()) < math.radians(2)               # The legs set it upright.


def test_a_badly_tilted_touchdown_tips_over():
    # Past about 23 degrees (atan(2.2 / 5.2)) the center of mass is beyond the lower foot.
    rocket = fly(placed_rocket(0.3, angle_degrees=40), 0.0, 0.0, seconds=10)
    assert rocket.status == "crashed"
    assert "body" in rocket.crash_reason


def test_friction_stops_a_sideways_touchdown():
    rocket = fly(placed_rocket(0.3, vx=2.0), 0.0, 0.0, seconds=10)
    assert rocket.status == "landed"
    assert rocket.vx == pytest.approx(0.0, abs=0.6)


def test_a_calm_landing_away_from_the_pad_is_off_pad():
    rocket = fly(placed_rocket(0.3, x=-10.0), 0.0, 0.0, seconds=10)
    assert rocket.status == "off_pad"


# --- Determinism --------------------------------------------------------------

def test_same_inputs_always_give_the_same_flight():
    def scripted_flight():
        rocket = still_rocket()
        for i in range(600):
            rocket.step(0.4 + 0.3 * math.sin(i / 20), math.sin(i / 35))
        return rocket

    # vars() lists every attribute, so the whole state must match exactly, not approximately.
    assert vars(scripted_flight()) == vars(scripted_flight())
