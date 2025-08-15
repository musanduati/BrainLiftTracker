#!/usr/bin/env python3
"""
Human-like behavior patterns for Twitter automation
"""

import random
import time
import math
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

class HumanBehavior:
    """Simulate human-like behavior patterns"""
    
    def __init__(self, driver):
        self.driver = driver
        self.action_chains = ActionChains(driver)
    
    def human_delay(self, min_sec=1, max_sec=3):
        """Human-like delay with slight randomization"""
        base_delay = random.uniform(min_sec, max_sec)
        # Add micro-variations (humans aren't perfectly consistent)
        micro_variation = random.uniform(-0.1, 0.1)
        total_delay = max(0.1, base_delay + micro_variation)
        time.sleep(total_delay)
    
    def typing_delay(self, text_length):
        """Realistic typing delay based on text length"""
        # Average human typing speed: 40 WPM = 200 characters/minute
        base_time = text_length / 200 * 60  # Convert to seconds
        variation = random.uniform(0.8, 1.2)  # ±20% variation
        return max(0.5, base_time * variation)
    
    def human_type(self, element, text, clear_first=True):
        """Type text with human-like patterns"""
        if clear_first:
            element.clear()
            self.human_delay(0.2, 0.5)
        
        # Sometimes type in chunks (like humans do)
        if len(text) > 10 and random.random() < 0.3:
            chunks = self._split_into_chunks(text)
            for chunk in chunks:
                element.send_keys(chunk)
                self.human_delay(0.1, 0.3)
        else:
            # Single typing with realistic speed
            for char in text:
                element.send_keys(char)
                # Slight delay between characters
                char_delay = random.uniform(0.05, 0.15)
                # Longer delays for spaces and punctuation (natural)
                if char in ' .,!?':
                    char_delay *= random.uniform(1.5, 2.5)
                time.sleep(char_delay)
    
    def _split_into_chunks(self, text):
        """Split text into realistic typing chunks"""
        words = text.split()
        chunks = []
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            # Chunk every 2-4 words
            if len(current_chunk) >= random.randint(2, 4):
                chunks.append(' '.join(current_chunk))
                current_chunk = []
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def random_mouse_movement(self):
        """Subtle mouse movements (humans don't keep mouse perfectly still)"""
        try:
            # Get viewport size
            viewport_width = self.driver.execute_script("return window.innerWidth")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            # Small random movements within viewport
            x_offset = random.randint(-50, 50)
            y_offset = random.randint(-50, 50)
            
            # Ensure we stay within bounds
            target_x = max(50, min(viewport_width - 50, viewport_width // 2 + x_offset))
            target_y = max(50, min(viewport_height - 50, viewport_height // 2 + y_offset))
            
            self.action_chains.move_by_offset(x_offset, y_offset).perform()
            
        except Exception:
            pass  # Mouse movement is optional
    
    def reading_pause(self, content_length=100):
        """Simulate time needed to read content"""
        # Average reading speed: 200-250 WPM
        words = content_length / 5  # Estimate words from character count
        reading_time = words / 225 * 60  # Convert to seconds
        
        # Add human variation
        variation = random.uniform(0.7, 1.3)
        pause_time = max(0.5, reading_time * variation)
        
        # Cap at reasonable maximum
        pause_time = min(pause_time, 3.0)
        
        time.sleep(pause_time)
    
    def scroll_behavior(self, element=None):
        """Human-like scrolling patterns"""
        if element:
            # Scroll within specific element
            self.driver.execute_script(
                "arguments[0].scrollTop += arguments[1];", 
                element, 
                random.randint(100, 300)
            )
        else:
            # Page scroll
            scroll_amount = random.randint(200, 500)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        
        # Pause after scrolling (humans don't scroll continuously)
        self.human_delay(0.5, 1.5)
    
    def occasional_pause(self, probability=0.1):
        """Occasional longer pauses (humans get distracted)"""
        if random.random() < probability:
            pause_time = random.uniform(2, 5)
            time.sleep(pause_time)
    
    def realistic_click_delay(self):
        """Delay between seeing something and clicking it"""
        # Humans need time to process visual information
        reaction_time = random.uniform(0.3, 0.8)
        time.sleep(reaction_time)
