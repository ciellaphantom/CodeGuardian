import requests

res = requests.get("http://127.0.0.1:8000/scans")
print("Status:", res.status_code)
print(res.json())
