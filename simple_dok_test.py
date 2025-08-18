#!/usr/bin/env python3
"""
Simple test for DOK patterns without emoji encoding issues
"""

import sys
import os

# Add the app directory to the path so we can import the DOK parser
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.dok_parser import parse_dok_metadata

# Test the key patterns we care about including actual tweet format
test_cases = [
    ("ADDED: DOK3: New feature", ("DOK3", "ADDED")),
    ("DELETED: DOK4: Removed feature", ("DOK4", "DELETED")), 
    ("UPDATED: DOK3: Modified feature", ("DOK3", "UPDATED")),
    ("UPDATED: DOK4: Enhanced feature", ("DOK4", "UPDATED")),
    # Test actual format from your tweets
    ("🔄 UPDATED: DOK4 (59% similarity): Fourth DOK4 added...", ("DOK4", "UPDATED")),
    ("🔄 UPDATED: DOK3 (71% similarity): SPOV 4.1: Copy is for lurkers...", ("DOK3", "UPDATED")),
    ("Regular tweet", (None, None))
]

print("Testing DOK Pattern Recognition")
print("-" * 40)

all_passed = True
for i, (tweet, expected) in enumerate(test_cases, 1):
    result = parse_dok_metadata(tweet)
    status = "PASS" if result == expected else "FAIL"
    if result != expected:
        all_passed = False
    
    print(f"{i}. {status}: '{tweet}' -> {result}")

print("-" * 40)
if all_passed:
    print("SUCCESS: All tests passed! UPDATED pattern works correctly.")
else:
    print("ERROR: Some tests failed.")