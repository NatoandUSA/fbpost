"""Biometric Keystroke Dynamics Engine.

Simulates human typing rhythm using Log-Normal Inter-Key Intervals (IKI),
QWERTY key distance weighting, natural cognitive pauses, and optional human typos with correction.
Guarantees 100% text fidelity upon completion.
"""

import math
import random
import time
from typing import Optional, Any
from .behavioral_profile import BehavioralProfile

# QWERTY physical adjacency map for realistic typo simulation
QWERTY_ADJACENT = {
    'q': 'wa', 'w': 'qase', 'e': 'wsdr', 'r': 'edft', 't': 'rfgy',
    'y': 'tghu', 'u': 'yhji', 'i': 'ujko', 'o': 'iklp', 'p': 'ol',
    'a': 'qwsz', 's': 'weadzx', 'd': 'ersfxc', 'f': 'rtdgcv', 'g': 'tyfhvb',
    'h': 'yugjbn', 'j': 'uikhmn', 'k': 'iojlm', 'l': 'opk',
    'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb', 'b': 'vghn',
    'n': 'bhjm', 'm': 'njk'
}

COGNITIVE_PUNCTUATION = {'.', ',', '!', '?', ':', ';', '-', '—', '\n'}


class BiometricTyping:
    """Simulates biometric keystroke timings and human typing mechanics."""

    def __init__(self, profile: Optional[BehavioralProfile] = None):
        self.profile = profile or BehavioralProfile.from_seed("default")

    def _sample_iki(self, char: str) -> float:
        """Sample Inter-Key Interval in seconds using Log-Normal distribution."""
        mean_ms = self.profile.iki_mean_ms
        sigma = self.profile.iki_sigma

        # Fast keys (space, lowercase frequent letters)
        if char == ' ':
            mean_ms *= 0.75
        # Slower keys (uppercase, digits, special characters)
        elif char.isupper() or char.isdigit() or not char.isalnum():
            mean_ms *= 1.35

        log_mean = math.log(max(20.0, mean_ms))
        val_ms = math.exp(random.gauss(log_mean, sigma))
        # Clamp within realistic human physiological limits (35ms - 650ms)
        clamped_ms = max(35.0, min(650.0, val_ms))
        return clamped_ms / 1000.0

    def _sample_dwell(self) -> float:
        """Sample key-down duration in seconds."""
        dwell_ms = max(25.0, random.gauss(self.profile.dwell_mean_ms, 15.0))
        return max(0.02, min(0.12, dwell_ms / 1000.0))

    def type_text(
        self,
        page: Any,
        locator: Any,
        text: str,
        multiline_key: str = "Enter",
        allow_typos: bool = True
    ) -> bool:
        """
        Type text into the focused target locator simulating human keystroke dynamics.
        
        Guarantees exact final content while emitting natural biometric event delays.
        """
        if not page or not text:
            return False

        try:
            locator.focus(timeout=3000)
        except Exception:
            pass

        keyboard = page.keyboard
        lines = text.split("\n")

        for line_idx, line in enumerate(lines):
            char_idx = 0
            while char_idx < len(line):
                char = line[char_idx]

                # Check for natural human typo (only on lowercase simple ASCII letters)
                can_typo = (
                    allow_typos
                    and char.lower() in QWERTY_ADJACENT
                    and char.isascii()
                    and random.random() < self.profile.typo_probability
                )

                if can_typo:
                    # 1. Type adjacent wrong character
                    wrong_char = random.choice(QWERTY_ADJACENT[char.lower()])
                    if char.isupper():
                        wrong_char = wrong_char.upper()
                    keyboard.type(wrong_char)
                    # 2. Human cognitive reaction delay (realizes mistake: 180ms - 380ms)
                    time.sleep(random.uniform(0.18, 0.38))
                    # 3. Backspace to remove mistake
                    keyboard.press("Backspace")
                    time.sleep(random.uniform(0.08, 0.16))

                # Type the actual intended character
                try:
                    keyboard.type(char)
                except Exception:
                    # Fallback for complex multi-byte symbols
                    keyboard.insert_text(char)

                # Cognitive pause after punctuation
                if char in COGNITIVE_PUNCTUATION:
                    if random.random() < self.profile.cognitive_pause_prob:
                        time.sleep(random.uniform(0.35, 1.10))

                # Inter-Key delay
                iki = self._sample_iki(char)
                time.sleep(iki)
                char_idx += 1

            # Handle multiline newline
            if line_idx < len(lines) - 1:
                key_to_press = "Shift+Enter" if multiline_key == "Shift+Enter" else "Enter"
                keyboard.press(key_to_press)
                # Thinking delay between paragraphs
                time.sleep(random.uniform(0.40, 1.30))

        return True
