# RocketLander

A 2D rocket landing game built from scratch, step by step, and later an AI agent
that learns to land the rocket by itself with reinforcement learning.

## Setup (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Play

```powershell
.\.venv\Scripts\python.exe main.py
```

W / S raise and lower the throttle, A / D swivel the engine nozzle, R restarts, Esc quits.

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests in `test_physics.py` check the flight physics in `physics.py`: gravity,
thrust, fuel, the nozzle, steering, and that the same inputs always give the same flight.

## Progress

- [x] Phase 0: project setup (folder, virtual environment, pygame, git)
- [ ] Phase 1: the game
- [ ] Phase 2: the RL environment
- [ ] Phase 3: learning
