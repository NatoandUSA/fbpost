"""High-Tech Human Behavior Simulation & Anti-Checkpoint Engine.

Sub-project module providing human-like biometric typing, kinematic Bézier mouse movement,
kinetic scrolling, and persona-based behavioral entropy for browser automation.
"""

from .engine import HumanEngine
from .behavioral_profile import BehavioralProfile
from .kinematic_mouse import KinematicMouse
from .biometric_typing import BiometricTyping
from .kinetic_scroll import KineticScroll

__all__ = [
    "HumanEngine",
    "BehavioralProfile",
    "KinematicMouse",
    "BiometricTyping",
    "KineticScroll",
]
