#!/usr/bin/env python3
"""Launch the real app window for a few seconds, then exit (CI smoke run)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("KIVY_HOME", os.path.join(BASE, "..", "tmp", "kivy"))
os.environ.setdefault("AUTO_ACCOUNT_DATA_DIR", os.path.join(BASE, "..", "tmp", "smoke"))
os.environ["KIVY_NO_ARGS"] = "1"
sys.path.insert(0, os.path.join(BASE, "src"))

from kivy.clock import Clock  # noqa: E402

from ui.app import AutoAccountApp  # noqa: E402


def main():
    app = AutoAccountApp()
    Clock.schedule_once(lambda dt: app.stop(), 5)
    app.run()
    print("app started and stopped cleanly")


if __name__ == "__main__":
    main()
