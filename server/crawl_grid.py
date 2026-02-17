import requests

class CrawlGrid:
    def __init__(self, remote_urls: list[str]):
        self.remote_urls = remote_urls
        self.ports = []

    def launch_grid(self, instances: int=1):
        for remote_url in self.remote_urls:
            for port in range(9222, 9222 + instances):
                try:
                    response = requests.get(f"{remote_url}/launch/{port}", )
                    if response.status_code == 200:
                        self.ports.append(port)
                        print(f"Browser launched on {remote_url}")
                except Exception as e:
                    print(f"Failed to launch browser on {remote_url}: {e}")

    def close_grid(self):
        for remote_url in self.remote_urls:
            try:
                ports = requests.get(f"{remote_url}/list-browsers").json()
                for port in ports:
                    response = requests.get(f"{remote_url}/kill/{port}", )
                    if response.status_code == 200:
                        print(f"Browser closed on {remote_url} port {port}")
            except Exception as e:
                print(f"Failed to close browser on {remote_url}: {e}")
