"""Optional Interaction Pacing Engine.

Sub-project module providing paced typing, kinematic pointer movement, and kinetic scrolling for browser UI automation.
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
