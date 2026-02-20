import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_DIR = os.path.dirname(THIS_DIR)

APP_DIR = os.path.join(PROJECT_DIR, "app")

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
