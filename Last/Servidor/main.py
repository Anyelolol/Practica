import subprocess
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "Pages", "L_Server_login.py")])
