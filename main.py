#!/usr/bin/env python3
"""
Auto Account - 全自动记账本
Main entry point
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ui.app import AutoAccountApp

if __name__ == '__main__':
    AutoAccountApp().run()