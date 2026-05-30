"""
EyeGuard - Thiết bị nhắc nhở chống mỏi mắt và mệt mỏi
Entry point chính của ứng dụng
"""

import sys
import os

# =========================================================
# THÊM ROOT PROJECT VÀO PYTHON PATH
# =========================================================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# =========================================================
# IMPORT APP
# =========================================================
from src.app import EyeGuardApp


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":

    app = EyeGuardApp()

    app.run()