import asyncio
import httpx


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


if __name__ == "__main__":
    crawl_grid = CrawlGrid(["http://localhost:8000"])

    asyncio.run(crawl_grid.close_grid())
    # asyncio.run(crawl_grid.launch_grid(instances=50))
