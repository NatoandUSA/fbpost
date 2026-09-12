"""Behavioral Persona & Entropy Profiler.

Generates deterministic, unique behavioral parameters for each account/profile ID
so that an account exhibits consistent human biometric characteristics across sessions
rather than completely random or robotic behavior.
"""

import hashlib
from dataclasses import dataclass


@dataclass
class BehavioralProfile:
    profile_id: str
    wpm: float                  # Base Words Per Minute (45 - 80)
    iki_mean_ms: float          # Inter-Key Interval mean in ms (~100 - 180)
    iki_sigma: float            # Log-normal standard deviation (0.25 - 0.40)
    dwell_mean_ms: float        # Keystroke down-time in ms (~50 - 90)
    cognitive_pause_prob: float # Probability of hesitation at punctuation (~0.25 - 0.50)
    mouse_speed_factor: float   # Mouse velocity multiplier (~0.85 - 1.25)
    mouse_overshoot_prob: float # Probability of mouse overshooting target (~0.10 - 0.25)
    scroll_impulse_factor: float# Scroll force multiplier (~0.80 - 1.20)
    typo_probability: float     # Chance of a typo with auto-correction (~0.005 - 0.02)
    device_type: str            # "desktop_mouse" or "trackpad"
    double_tap_factor: float    # Speedup factor for consecutive identical keys (0.60 - 0.75)
    fatigue_rate: float         # Speed degradation rate on long texts (0.03 - 0.08)
    mouse_wheel_type: str       # "discrete_wheel" (notched) or "smooth_touchpad"

    @classmethod
    def from_seed(cls, seed_id: str = "default") -> "BehavioralProfile":
        """Generate a consistent persona profile based on the given account/profile ID."""
        clean_seed = str(seed_id or "default").strip().lower()
        digest = hashlib.sha256(clean_seed.encode("utf-8")).digest()
        
        # Derive deterministic pseudo-random parameters from hash bytes
        wpm = 48.0 + (digest[0] / 255.0) * 32.0  # 48 to 80 WPM
        iki_mean_ms = (60.0 / (wpm * 5.0)) * 1000.0  # standard ~5 chars/word formula
        iki_sigma = 0.25 + (digest[1] / 255.0) * 0.15 # 0.25 to 0.40
        dwell_mean_ms = 50.0 + (digest[2] / 255.0) * 40.0 # 50 to 90 ms
        cognitive_pause_prob = 0.25 + (digest[3] / 255.0) * 0.25 # 25% to 50%
        mouse_speed = 0.85 + (digest[4] / 255.0) * 0.40 # 0.85 to 1.25
        overshoot_prob = 0.10 + (digest[5] / 255.0) * 0.15 # 10% to 25%
        scroll_factor = 0.85 + (digest[6] / 255.0) * 0.35 # 0.85 to 1.20
        typo_prob = 0.006 + (digest[7] / 255.0) * 0.012 # 0.6% to 1.8%
        
        # Additional biometric parameters
        device_type = "desktop_mouse" if digest[8] % 2 == 0 else "trackpad"
        double_tap_factor = 0.60 + (digest[9] / 255.0) * 0.15 # 0.60 to 0.75
        fatigue_rate = 0.03 + (digest[10] / 255.0) * 0.05 # 3% to 8%
        mouse_wheel_type = "discrete_wheel" if digest[11] % 2 == 0 else "smooth_touchpad"

        return cls(
            profile_id=clean_seed,
            wpm=round(wpm, 1),
            iki_mean_ms=round(iki_mean_ms, 1),
            iki_sigma=round(iki_sigma, 3),
            dwell_mean_ms=round(dwell_mean_ms, 1),
            cognitive_pause_prob=round(cognitive_pause_prob, 3),
            mouse_speed_factor=round(mouse_speed, 3),
            mouse_overshoot_prob=round(overshoot_prob, 3),
            scroll_impulse_factor=round(scroll_factor, 3),
            typo_probability=round(typo_prob, 4),
            device_type=device_type,
            double_tap_factor=round(double_tap_factor, 3),
            fatigue_rate=round(fatigue_rate, 3),
            mouse_wheel_type=mouse_wheel_type,
        )
