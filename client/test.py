import concurrent.futures
import requests
import time

def launch_one(port):
    start = time.time()
    r = requests.get(f"http://localhost:8000/launch/{port}")
    print(f"Port {port} killed in {time.time() - start:.2f}s")
    return r.json()

# This sends all 5 requests at the exact same time
ports = [5000, 5001, 5002, 5003, 5004]
with concurrent.futures.ThreadPoolExecutor() as executor:
    executor.map(launch_one, ports)

