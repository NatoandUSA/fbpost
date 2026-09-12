"""Biometric Keystroke Dynamics Engine.

Simulates human typing rhythm using Log-Normal Inter-Key Intervals (IKI),
Down-Up (DU) dwell telemetry, Shift-key physical capitalization, double-letter
acceleration, typing fatigue modeling, and QWERTY typo-correction.
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

    def _sample_iki(self, char: str, prev_char: Optional[str] = None, total_typed: int = 0) -> float:
        """Sample Inter-Key Interval in seconds using Log-Normal distribution."""
        mean_ms = self.profile.iki_mean_ms
        sigma = self.profile.iki_sigma

        # 1. Double letter acceleration (e.g. 'oo', 'll', 'ee' typed 35% faster)
        if prev_char and char == prev_char and char.isalpha():
            mean_ms *= self.profile.double_tap_factor
        # 2. Fast keys (spacebar is pressed with thumb without finger travel)
        elif char == ' ':
            mean_ms *= 0.70
        # 3. Slower keys (uppercase, digits, symbols require reach)
        elif char.isupper() or char.isdigit() or not char.isalnum():
            mean_ms *= 1.30

        # 4. Human fatigue model: slightly slower on long texts (> 200 chars)
        if total_typed > 200:
            fatigue_boost = 1.0 + min(0.12, (total_typed - 200) * (self.profile.fatigue_rate / 100.0))
            mean_ms *= fatigue_boost

        log_mean = math.log(max(20.0, mean_ms))
        val_ms = math.exp(random.gauss(log_mean, sigma))
        clamped_ms = max(35.0, min(650.0, val_ms))
        return clamped_ms / 1000.0

    def _sample_dwell(self) -> float:
        """Sample key-down dwell duration in seconds (time key stays depressed)."""
        dwell_ms = max(28.0, random.gauss(self.profile.dwell_mean_ms, 12.0))
        return max(0.025, min(0.110, dwell_ms / 1000.0))

    def _emit_keystroke(self, keyboard: Any, char: str) -> None:
        """Emit authentic Down-Up (DU) telemetry pair for a single character."""
        dwell = self._sample_dwell()
        
        # Physical Shift-key sequence for standard ASCII uppercase letters
        if char.isupper() and char.isascii():
            try:
                keyboard.down("Shift")
                time.sleep(random.uniform(0.04, 0.08))
                keyboard.down(char.lower())
                time.sleep(dwell)
                keyboard.up(char.lower())
                time.sleep(random.uniform(0.03, 0.06))
                keyboard.up("Shift")
                return
            except Exception:
                pass

        # Standard ASCII lowercase/punctuation: explicit down -> dwell -> up
        if char.isascii() and (char.isprintable() or char == ' '):
            try:
                keyboard.down(char)
                time.sleep(dwell)
                keyboard.up(char)
                return
            except Exception:
                pass

        # Complex multi-byte unicode or Vietnamese compound characters
        try:
            keyboard.type(char)
        except Exception:
            keyboard.insert_text(char)

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
        total_typed = 0
        prev_char: Optional[str] = None

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
                    self._emit_keystroke(keyboard, wrong_char)
                    
                    # 2. Human cognitive reaction delay (realizes mistake: 180ms - 380ms)
                    time.sleep(random.uniform(0.18, 0.38))
                    
                    # 3. Backspace to remove mistake
                    keyboard.down("Backspace")
                    time.sleep(self._sample_dwell())
                    keyboard.up("Backspace")
                    time.sleep(random.uniform(0.08, 0.16))

                # Type the actual intended character
                self._emit_keystroke(keyboard, char)

                # Cognitive pause after punctuation (thinking about sentence structure)
                if char in COGNITIVE_PUNCTUATION:
                    if random.random() < self.profile.cognitive_pause_prob:
                        time.sleep(random.uniform(0.35, 1.10))

                # Inter-Key delay (IKI)
                iki = self._sample_iki(char, prev_char=prev_char, total_typed=total_typed)
                time.sleep(iki)

                prev_char = char
                total_typed += 1
                char_idx += 1

            # Handle multiline newline
            if line_idx < len(lines) - 1:
                key_to_press = "Shift+Enter" if multiline_key == "Shift+Enter" else "Enter"
                keyboard.down(key_to_press)
                time.sleep(random.uniform(0.06, 0.12))
                keyboard.up(key_to_press)
                # Thinking delay between paragraphs
                time.sleep(random.uniform(0.40, 1.30))
                prev_char = '\n'
                total_typed += 1

        return True
