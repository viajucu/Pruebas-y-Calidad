import os
import sys

# Ruta absoluta
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(THIS_DIR), "app")

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
