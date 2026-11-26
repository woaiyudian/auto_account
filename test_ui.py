"""Headless-ish smoke test: build the UI, enter every screen, then quit."""
import os
import sys

os.environ.setdefault("KIVY_HOME", os.path.join(os.path.dirname(__file__), "..", "tmp", "kivy"))
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ["KIVY_NO_CONSOLELOG"] = "0"

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from kivy.clock import Clock  # noqa: E402

from ui.app import AutoAccountApp  # noqa: E402

SCREENS = ["home", "add_txn", "transactions", "savings", "add_savings",
           "scheduled", "add_task", "settings"]


def main():
    app = AutoAccountApp()
    app.run = lambda: None  # do not start the event loop yet
    root = app.build()
    print("[smoke] build ok, screens:", list(root.screen_names))

    for name in SCREENS:
        screen = root.get_screen(name)
        root.current = name
        screen.on_pre_enter()
        print(f"[smoke] entered {name}: {type(screen).__name__} widgets={len(screen.children)}")

    print("[smoke] OK")


if __name__ == "__main__":
    sys.exit(main())
