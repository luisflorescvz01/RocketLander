"""Automated checks for the flight physics in physics.py. Run them with: pytest"""

import math

import pytest

from physics import (
    DT, GRAVITY, DRY_MASS, START_FUEL, MAX_THRUST, MAX_FUEL_FLOW,
    MAX_GIMBAL, GIMBAL_RATE, Rocket,
)


def still_rocket():
    """A fresh rocket at the usual height, but centered with no sideways drift."""
    rocket = Rocket()
    rocket.x = 0.0
    rocket.vx = 0.0
    return rocket


def fly(rocket, throttle, gimbal_command, seconds):
    """Hold the same controls for a number of seconds (or until the flight ends)."""
    for _ in range(round(seconds / DT)):
        if rocket.status != "flying":
            break
        rocket.step(throttle, gimbal_command)
    return rocket


# --- Gravity ------------------------------------------------------------------

def test_free_fall_from_40_m_takes_about_2_86_seconds():
    rocket = fly(still_rocket(), 0.0, 0.0, seconds=10)
    # Exact physics: t = sqrt(2h / g). Our 1/60 s steps land within one step of it.
    assert rocket.time == pytest.approx(math.sqrt(2 * 40 / GRAVITY), abs=DT)


def test_free_fall_from_40_m_hits_at_about_28_m_per_s():
    rocket = fly(still_rocket(), 0.0, 0.0, seconds=10)
    # Exact physics: v = sqrt(2gh).
    assert rocket.impact_speed == pytest.approx(math.sqrt(2 * GRAVITY * 40), abs=0.2)


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


# --- Determinism --------------------------------------------------------------

def test_same_inputs_always_give_the_same_flight():
    def scripted_flight():
        rocket = still_rocket()
        for i in range(600):
            rocket.step(0.4 + 0.3 * math.sin(i / 20), math.sin(i / 35))
        return rocket

    # vars() lists every attribute, so the whole state must match exactly, not approximately.
    assert vars(scripted_flight()) == vars(scripted_flight())
