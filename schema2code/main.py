#!/usr/bin/env python3
"""
schema2code - A tool for converting JSON schemas to programming language types
"""

import os
import sys

# Add the parent directory to sys.path to allow importing from src
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Now we can import from src
from src.main import main

# Re-export the main function
__all__ = ['main']

if __name__ == '__main__':
    main()
