"""
run_client.py - Khởi động Máy trạm Khách hàng (Client GUI)
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from client.client_main import ClientApplication

if __name__ == "__main__":
    app = ClientApplication()
    app.run()
