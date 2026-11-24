"""Phase 0 check: prove that Python and pygame work in this project's environment."""

import sys

import pygame

print("Python:", sys.version.split()[0])
print("Running from:", sys.executable)
print("pygame:", pygame.version.ver)
