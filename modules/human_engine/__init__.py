"""High-Tech Human Behavior Simulation & Anti-Checkpoint Engine.

Sub-project module providing human-like biometric typing, kinematic Bézier mouse movement,
kinetic scrolling, stealth evasion scripts, and persona-based behavioral entropy for browser automation.
"""

from .engine import HumanEngine
from .behavioral_profile import BehavioralProfile
from .kinematic_mouse import KinematicMouse
from .biometric_typing import BiometricTyping
from .kinetic_scroll import KineticScroll
from .stealth_evasion import apply_stealth_scripts, STEALTH_INJECTION_SCRIPT

__all__ = [
    "HumanEngine",
    "BehavioralProfile",
    "KinematicMouse",
    "BiometricTyping",
    "KineticScroll",
    "apply_stealth_scripts",
    "STEALTH_INJECTION_SCRIPT",
]
