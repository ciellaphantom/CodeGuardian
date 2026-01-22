import requests

code = """
password = "hardcoded_secret_123"

import subprocess
subprocess.Popen("ls", shell=True)

eval("1+1")
"""

resp = requests.post(
    "http://127.0.0.1:8000/scan",
    json={"code": code},
)

print("Status:", resp.status_code)
print("JSON:", resp.json())
