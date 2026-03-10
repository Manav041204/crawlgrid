import asyncio
import httpx
import time
import json
import random
from contextlib import asynccontextmanager
from typing import List, Optional, Dict

class BrowserSession:
    """
    A stateful session object that represents a locked tab.
    The user interacts with this object to perform sequential actions.
    """
    def __init__(self, grid, remote_url: str, tab_id: str, port: int, initial_url: str):
        self.grid = grid
        self.remote_url = remote_url
        self.tab_id = tab_id
        self.port = port
        self.url = initial_url
        self._listener_task = None

    async def input(self, text: str, xpath: str, timeout: int = 10):
        """Type text into an element."""
        return await self.grid.input_element(
            self.tab_id, self.port, self.url, text, xpath, 
            timeout=timeout, remote_url=self.remote_url, release=False
        )

    async def click(self, xpath: str, timeout: int = 10):
        """Click an element."""
        return await self.grid.click_element(
            self.tab_id, self.port, self.url, xpath, 
            timeout=timeout, remote_url=self.remote_url, release=False
        )

    async def screenshot(self, filename: str = "capture.png"):
        """Take a screenshot of the current state."""
        return await self.grid.capture_screenshot(
            self.tab_id, filename, remote_url=self.remote_url, release=False
        )

    async def start_listening(self, targets: str = None):
        """Starts network interception for this specific session."""
        self._listener_task = asyncio.create_task(
            self.grid.stream_network(self.tab_id, targets, remote_url=self.remote_url)
        )
        print(f"📡 Listener attached to Session {self.tab_id}")

    async def stop_listening(self):
        """Stops network interception for this specific session."""
        await self.grid.stop_listen(self.tab_id, remote_url=self.remote_url)
        if self._listener_task:
            self._listener_task.cancel()

class CrawlGrid:
    def __init__(self, remote_urls: List[str]):
        self.remote_urls = remote_urls

    # --- INFRASTRUCTURE & SCALING ---

    async def launch_grid(self, instances: int = 1):
        async with httpx.AsyncClient() as client:
            tasks = []
            for remote_url in self.remote_urls:
                for port in range(9222, 9222 + instances):
                    tasks.append(self._launch_instance(client, remote_url, port))
            await asyncio.gather(*tasks)

    async def _launch_instance(self, client, remote_url, port):
        try:
            response = await client.get(f"{remote_url}/launch", params={"port": port})
            if response.status_code == 200:
                print(f"✅ Browser launched: {remote_url} port {port}")
        except Exception as e:
            print(f"❌ Launch Failed on {remote_url}: {e}")

    async def distribute_tabs(self, total_tabs: int = 0, tab_per_browser: int = 0):
        async with httpx.AsyncClient() as client:
            tasks = []
            for remote_url in self.remote_urls:
                params = {"total_tabs": total_tabs} if total_tabs > 0 else {"tab_per_browser": tab_per_browser}
                tasks.append(client.get(f"{remote_url}/launch-tabs", params=params, timeout=60.0))
            await asyncio.gather(*tasks)
            print(f"📊 Tabs distributed across {len(self.remote_urls)} nodes.")

    # --- LOAD BALANCING & SESSION LOGIC ---

    async def _get_best_node(self) -> str:
        """Finds the node with the most available (idle) tabs."""
        best_url = self.remote_urls[0]
        max_idle = -1
        # async with httpx.AsyncClient() as client:
        #     for url in self.remote_urls:
        #         try:
        #             resp = await client.get(f"{url}/status", timeout=2.0)
        #             idle = resp.json().get("idle_tabs", 0)
        #             if idle > max_idle:
        #                 max_idle = idle
        #                 best_url = url
        #         except: continue
        return best_url

    @asynccontextmanager
    async def get_session(self, url: str):
        """Context manager to handle tab acquisition and automatic release."""
        remote_url = await self._get_best_node()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{remote_url}/get-url", params={"url": url, "release_tab": False})
            if resp.status_code != 200:
                raise Exception(f"Grid Capacity Full on {remote_url} {resp.json()} {resp.status_code}")
            
            data = resp.json()
            session = BrowserSession(self, remote_url, data['tab_id'], data['port'], url)
            try:
                yield session
            finally:
                # Cleanup: Stop listeners and release tab
                await session.stop_listening()
                await client.post(f"{remote_url}/release-tab", params={"tab_id": session.tab_id})

    # --- CORE ACTION COMMANDS ---

    async def input_element(self, tab_id, port, url, input_text, xpath, timeout=10, remote_url=None, release=True):
        target = remote_url or self.remote_urls[0]
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(f"{target}/get-element", params={
                    "tab_id": tab_id, "input_text": input_text, "xpath": xpath, "timeout": timeout
                })
                return resp.json()
            finally:
                if release: await client.post(f"{target}/release-tab", params={"tab_id": tab_id})

    async def click_element(self, tab_id, port, url, xpath, timeout=10, remote_url=None, release=True):
        target = remote_url or self.remote_urls[0]
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(f"{target}/get-element", params={
                    "tab_id": tab_id, "xpath": xpath, "click": True, "timeout": timeout
                })
                return resp.json()
            finally:
                if release: await client.post(f"{target}/release-tab", params={"tab_id": tab_id})

    async def capture_screenshot(self, tab_id, filename, remote_url=None, release=False):
        target = remote_url or self.remote_urls[0]
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{target}/screenshot", params={"tab_id": tab_id, "name": filename})
                if resp.status_code == 200:
                    with open(filename, "wb") as f:
                        f.write(resp.content)
                    return filename
            finally:
                if release: await client.post(f"{target}/release-tab", params={"tab_id": tab_id})

    # --- NETWORK STREAMING COMMANDS ---

    async def stream_network(self, tab_id: str, targets: str = None, remote_url=None):
        target = remote_url or self.remote_urls[0]
        url = f"{target}/listen"
        params = {"tab_id": tab_id, "targets": targets} if targets else {"tab_id": tab_id}
        
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", url, params=params) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            packet = json.loads(line[6:])
                            print(f"📦 [Tab {tab_id}] {packet['method']} | {packet['url']} | Status: {packet['status']}")
        except asyncio.CancelledError:
            pass 
        except Exception as e:
            print(f"🛑 [Stream Error] {e}")

    async def stop_listen(self, tab_id: str, remote_url=None):
        target = remote_url or self.remote_urls[0]
        async with httpx.AsyncClient() as client:
            await client.get(f"{target}/stop-listen", params={"tab_id": tab_id})

    async def close_grid(self):
        async with httpx.AsyncClient() as client:
            for remote_url in self.remote_urls:
                try:
                    resp = await client.get(f"{remote_url}/list-browsers")
                    for port in resp.json():
                        await client.get(f"{remote_url}/kill", params={"port": port})
                except: pass

if __name__ == "__main__":
    async def browse_task(grid: CrawlGrid, task_id: int, search_term: str):
        """A single worker task that uses a session."""
        print(f"🚀 Task {task_id}: Starting search for '{search_term}'")
        
        try:
            async with grid.get_session("https://www.google.com") as session:
                await session.start_listening(targets="google")
                
                await session.input(search_term, "//textarea[@name='q']")
                await session.click("//input[@name='btnK']")
                
                await asyncio.sleep(random.uniform(2, 4))
                
                filename = f"result_task_{task_id}.png"
                await session.screenshot(filename)
                print(f"✅ Task {task_id}: Finished. Screenshot saved as {filename}")
                
        except Exception as e:
            print(f"❌ Task {task_id} failed: {e}")

    async def run_stress_test():
        grid = CrawlGrid(["http://localhost:8000"])
        
        print("🛠️  Step 1: Launching 3 browser instances...")
        await grid.launch_grid(instances=3) 
        
        print("🛠️  Step 2: Distributing 4 tabs per browser (12 tabs total)...")
        await grid.distribute_tabs(total_tabs=12)

        queries = ["Python", "FastAPI", "Asyncio", "Httpx", "DrissionPage", 
                "Web Scraping", "Load Balancing", "Concurrency", "Docker", "Linux"]

        print(f"🔥 Step 3: Running {len(queries)} parallel sessions...")
        start_time = time.time()
        
        tasks = [browse_task(grid, i, queries[i]) for i in range(len(queries))]
        await asyncio.gather(*tasks)

        duration = time.time() - start_time
        print(f"\n✨ All tasks complete in {duration:.2f} seconds.")

    async def single_run_test():
    # 1. Initialize Grid (pointing to your local API)
        grid = CrawlGrid(["http://localhost:8000"])
        
        print("🛠️  Step 1: Launching 1 browser instance...")
        await grid.launch_grid(instances=1)
        
        print("🛠️  Step 2: Distributing 1 tab...")
        await grid.distribute_tabs(tab_per_browser=2)

        print("🚀 Step 3: Starting Single Session...")
        try:
            async with grid.get_session("https://www.google.com") as session:
                # A. Start Network Listener
                print("📡 Attaching listener...")
                await session.start_listening(targets="google")
                
                # B. Perform a simple search
                print("⌨️  Typing search query...")
                await session.input("FastAPI StreamingResponse", "//textarea[@name='q']")
                
                print("🖱️  Clicking search button...")
                await session.click("//input[@name='btnK']")
                
                # C. Wait for some packets to flow
                print("⏳ Waiting for network traffic...")
                await asyncio.sleep(5)
                
                # D. Capture final state
                print("📸 Taking screenshot...")
                await session.screenshot("single_test_result.png")
                
                print("✅ Actions completed. Exiting context manager (this triggers release).")

        except Exception as e:
            print(f"❌ Test Failed: {e}")
    
    asyncio.run(run_stress_test())
    # asyncio.run(single_run_test())