#!/usr/bin/env python3
"""
Example test file - SAFE FOR GITHUB

To run tests, copy this to test_local.py and add your API keys:
    cp test_example.py test_local.py
    # Edit test_local.py and add your keys
    python test_local.py
"""

import os

# Set your API keys here (in test_local.py, NOT in this file!)
os.environ["GLM_API_KEY"] = "your_glm_api_key"
os.environ["OPENROUTER_API_KEY"] = "your_openrouter_api_key"

# Your test code here...
print("⚠️ This is an example file. Copy to test_local.py and add your keys!")
