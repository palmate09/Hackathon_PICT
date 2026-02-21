import sys
import os

try:
    from app import app
    print("Backend loaded successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
