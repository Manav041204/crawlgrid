import asyncio
import httpx
import time

class CrawlGrid:
    def __init__(self, remote_urls: list[str]):
        self.remote_urls = remote_urls
        self.ports = []

    async def launch_grid(self, instances: int = 1):
        async with httpx.AsyncClient() as client:
            tasks = []

            for remote_url in self.remote_urls:
                for port in range(9222, 9222 + instances):
                    tasks.append(
                        self._launch_instance(client, remote_url, port)
                    )

            await asyncio.gather(*tasks)

    async def _launch_instance(self, client, remote_url, port):
        try:
            response = await client.get(f"{remote_url}/launch/{port}")
            if response.status_code == 200:
                self.ports.append(port)
                print(f"Browser launched on {remote_url} port {port}")
        except Exception as e:
            print(f"Failed to launch browser on {remote_url}: {e}")

    async def close_grid(self):
        async with httpx.AsyncClient() as client:
            tasks = []

            for remote_url in self.remote_urls:
                tasks.append(self._close_remote(client, remote_url))

            await asyncio.gather(*tasks)

    async def _close_remote(self, client, remote_url):
        try:
            response = await client.get(f"{remote_url}/list-browsers")
            ports = response.json()

            close_tasks = []
            for port in ports:
                close_tasks.append(
                    self._close_instance(client, remote_url, port)
                )

            await asyncio.gather(*close_tasks)

        except Exception as e:
            print(f"Failed to close browser on {remote_url}: {e}")

    async def _close_instance(self, client, remote_url, port):
        try:
            response = await client.get(f"{remote_url}/kill/{port}")
            if response.status_code == 200:
                print(f"Browser closed on {remote_url} port {port}")
        except Exception as e:
            print(f"Failed to close browser on {remote_url} port {port}: {e}")

    async def distribute_tabs(self, count: int):
        """Hits the /distribute-tabs endpoint to scale tab count across browsers."""
        remote_url = self.remote_urls[0]
        async with httpx.AsyncClient() as client:
            try:
                print(f"--- Requesting {count} additional tabs ---")
                response = await client.get(
                    f"{remote_url}/launch-tabs/{count}", 
                    timeout=60.0 # Opening many tabs can take time
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Distribution Success: {data['message']}")
                    print(f"📊 Report: {data.get('distribution')}")
                    return data
                else:
                    print(f"❌ Distribution Failed: {response.text}")
            except Exception as e:
                print(f"⚠️ Error hitting /launch-tabs: {e}")

    async def get_url(self, url: str):
        remote_url = self.remote_urls[0] 
        # Increase timeout significantly for 40 concurrent loads
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{remote_url}/get-url", 
                    params={"url": url}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Success: Port {data['port']} | Tab {data['tab_id']} -> {url}")
                    return data
                else:
                    # Actually print what the server said (e.g., "Capacity reached")
                    error_detail = response.json().get('detail', response.text)
                    print(f"❌ Server Rejected: {error_detail}")
                    return None
            except Exception as e:
                # This will now print the actual Python error (Timeout, ConnectionRefused, etc.)
                print(f"⚠️ Network/Request Error for {url}: {type(e).__name__} - {e}")
                return None

    async def test_get_url(self):
        urls = [
            "https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com","https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com","https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com","https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com", "https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com","https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com","https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com","https://google.com", "https://bing.com", "https://github.com",
            "https://python.org", "https://fastapi.tiangolo.com", "https://reddit.com",
            "https://stackoverflow.com", "https://wikipedia.org", "https://apple.com",
            "https://amazon.com",
            
        ]

        tasks = [self.get_url(url) for url in urls]
        results = await asyncio.gather(*tasks)

        successes = [r for r in results if r and r.get("status") == "success"]
        print(f"\n--- Final Results ---")
        print(f"Total Requests: {len(urls)}")
        print(f"Successful Navigations: {len(successes)}")
        print(f"Capacity Blocked: {len(urls) - len(successes)}")

if __name__ == "__main__":

    st = time.time()
    crawl_grid = CrawlGrid(["http://localhost:8000"])

    # 1. Clean up everything first
    asyncio.run(crawl_grid.close_grid())
    
    time.sleep(5)
    # 2. Start 2 browsers (Default 1 tab each = 2 tabs total)
    asyncio.run(crawl_grid.launch_grid(instances=4))

    # 3. Add 4 more tabs (Total 6 tabs)
    asyncio.run(crawl_grid.distribute_tabs(count=40))
    
    # 4. Run 10 URL requests (Should see 6 successes and 4 failures)
    asyncio.run(crawl_grid.test_get_url())

    tt = time.time() - st
    print(f"Total time: {tt}")