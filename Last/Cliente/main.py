import subprocess
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

subprocess.Popen(["python", os.path.join(BASE_DIR, "Pages", "L_Client_Login.py")])