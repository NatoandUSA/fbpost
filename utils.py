import re
import random
import time

def process_spintax(text):
    """
    Parses Spintax like {Hello|Hi|Hey} there!
    Supports simple, non-nested spintax.
    """
    if not text:
        return ""
    pattern = re.compile(r'\{([^{}]*)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        options = match.group(1).split('|')
        choice = random.choice(options)
        text = text[:match.start()] + choice + text[match.end():]
    return text

def human_type(page, locator, text):
    """
    Types text character by character with random delays and occasional simulated typos.
    """
    print("Typing with human-like behavior (including possible typos)...")
    locator.focus()
    keyboard = page.keyboard
    
    # Facebook inputs often need an initial click or it might miss the first char
    locator.click()
    time.sleep(random.uniform(0.5, 1.0))
    
    for char in text:
        # Special handling for newlines
        if char == '\n':
            keyboard.press('Enter')
            time.sleep(random.uniform(0.2, 0.5))
            continue
            
        # 3% chance to make a typo (if it's a common char)
        if char.isalpha() and random.random() < 0.03:
            # Type a random wrong character
            wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
            keyboard.type(wrong_char, delay=random.randint(30, 80))
            time.sleep(random.uniform(0.1, 0.4))
            # Delete it
            keyboard.press("Backspace")
            time.sleep(random.uniform(0.1, 0.3))
            
        # Type the correct character
        # We use insertText for complex unicode/emoji to avoid issues, 
        # but keyboard.type is better for simulating real keypresses.
        try:
            keyboard.type(char, delay=random.randint(30, 80))
        except:
            # Fallback for weird characters
            keyboard.insert_text(char)
            
        # Occasional longer pause (thinking pause)
        if char in ['.', ',', '!', '?', ' '] and random.random() < 0.1:
            time.sleep(random.uniform(0.4, 1.2))
