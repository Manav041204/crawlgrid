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
            response = await client.get(f"{remote_url}/launch", params={"port": port})
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
            response = await client.get(f"{remote_url}/kill", params={"port": port})
            if response.status_code == 200:
                print(f"Browser closed on {remote_url} port {port}")
        except Exception as e:
            print(f"Failed to close browser on {remote_url} port {port}: {e}")

    async def distribute_tabs(self, total_tabs: int = 0, tab_per_browser: int = 0):
        """Hits the /distribute-tabs endpoint to scale tab count across browsers."""
        remote_url = self.remote_urls[0]
        async with httpx.AsyncClient() as client:
            try:
                print(f"--- Requesting {total_tabs if total_tabs else tab_per_browser} additional tabs ---")
                response = await client.get(
                    f"{remote_url}/launch-tabs", 
                    params={"total_tabs": total_tabs} if total_tabs > 0 else {"tab_per_browser": tab_per_browser},
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
                    params={"url": url, "release_tab": False},
                    headers={
                        # 'content-length': '0',
                        # 'content-type': 'application/json'
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    tab_id = data['tab_id']
                    port = data['port']
                    await self.get_element(tab_id, port, url)
                    print(f"✅ Success: Port {port} | Tab {tab_id} -> {url}")
                    
                    # Release tab
                    await client.post(f"{remote_url}/release-tab", params={"tab_id": tab_id})
                    
                    return data
                else:
                    error_detail = response.json().get('detail', response.text)
                    print(f"❌ Server Rejected: {error_detail}")
                    return None
            except Exception as e:
                print(f"⚠️ Network/Request Error for {url}: {type(e).__name__} - {e}")
                return None
    
    async def get_element(self, tab_id, port, url):
        remote_url = self.remote_urls[0]
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{remote_url}/get-element", 
                    params={"tab_id": tab_id, "input_text": "Tshirt", "xpath": '//input[@id="twotabsearchtextbox"]'}
                )
                if response.status_code == 200:
                    data = response.json()
                    element_html = data.get('element_html', '')
                    html_snippet = element_html[:50] + "..." if element_html else "None"
                    print(f"✅ Success: Port {port} | Tab {tab_id} | element_html: {html_snippet} -> {url}")
                else:
                    print(f"⚠️ Failed to get element on Tab {tab_id}: {response.text}")
            except Exception as e:
                print(f"⚠️ get_element Error for {url}: {e}")

    async def test_get_url(self):
        urls = [
            "https://books.toscrape.com/catalogue/category/books/travel_2/index.html",
            "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html",
            "https://books.toscrape.com/catalogue/category/books/historical-fiction_4/index.html",
            "https://books.toscrape.com/catalogue/category/books/sequential-art_5/index.html",
            "https://books.toscrape.com/catalogue/category/books/classics_6/index.html",
            "https://books.toscrape.com/catalogue/category/books/philosophy_7/index.html",
            "https://books.toscrape.com/catalogue/category/books/romance_8/index.html",
            "https://books.toscrape.com/catalogue/category/books/womens-fiction_9/index.html",
            "https://books.toscrape.com/catalogue/category/books/fiction_10/index.html",
            "https://books.toscrape.com/catalogue/category/books/childrens_11/index.html",
            "https://books.toscrape.com/catalogue/category/books/religion_12/index.html",
            "https://books.toscrape.com/catalogue/category/books/nonfiction_13/index.html",
            "https://books.toscrape.com/catalogue/category/books/music_14/index.html",
            "https://books.toscrape.com/catalogue/category/books/default_15/index.html",
            "https://books.toscrape.com/catalogue/category/books/science-fiction_16/index.html",
            "https://books.toscrape.com/catalogue/category/books/sports-and-games_17/index.html",
            "https://books.toscrape.com/catalogue/category/books/add-a-comment_18/index.html",
            "https://books.toscrape.com/catalogue/category/books/fantasy_19/index.html",
            "https://books.toscrape.com/catalogue/category/books/new-adult_20/index.html",
            "https://books.toscrape.com/catalogue/category/books/young-adult_21/index.html",
            "https://books.toscrape.com/catalogue/category/books/science_22/index.html",
            "https://books.toscrape.com/catalogue/category/books/poetry_23/index.html",
            "https://books.toscrape.com/catalogue/category/books/paranormal_24/index.html",
            "https://books.toscrape.com/catalogue/category/books/art_25/index.html",
            "https://books.toscrape.com/catalogue/category/books/psychology_26/index.html",
            "https://books.toscrape.com/catalogue/category/books/autobiography_27/index.html",
            "https://books.toscrape.com/catalogue/category/books/parenting_28/index.html",
            "https://books.toscrape.com/catalogue/category/books/adult-fiction_29/index.html",
            "https://books.toscrape.com/catalogue/category/books/humor_30/index.html",
            "https://books.toscrape.com/catalogue/category/books/horror_31/index.html",
            "https://books.toscrape.com/catalogue/category/books/history_32/index.html",
            "https://books.toscrape.com/catalogue/category/books/food-and-drink_33/index.html",
            "https://books.toscrape.com/catalogue/category/books/christian-fiction_34/index.html",
            "https://books.toscrape.com/catalogue/category/books/business_35/index.html",
            "https://books.toscrape.com/catalogue/category/books/biography_36/index.html",
            "https://books.toscrape.com/catalogue/category/books/thriller_37/index.html",
            "https://books.toscrape.com/catalogue/category/books/contemporary_38/index.html",
            "https://books.toscrape.com/catalogue/category/books/spirituality_39/index.html",
            "https://books.toscrape.com/catalogue/category/books/academic_40/index.html",
            "https://books.toscrape.com/catalogue/category/books/self-help_41/index.html",
            "https://books.toscrape.com/catalogue/category/books/historical_42/index.html",
            "https://books.toscrape.com/catalogue/category/books/christian_43/index.html",
            "https://books.toscrape.com/catalogue/category/books/suspense_44/index.html",
            "https://books.toscrape.com/catalogue/category/books/short-stories_45/index.html",
            "https://books.toscrape.com/catalogue/category/books/novels_46/index.html",
            "https://books.toscrape.com/catalogue/category/books/health_47/index.html",
            "https://books.toscrape.com/catalogue/category/books/politics_48/index.html",
            "https://books.toscrape.com/catalogue/category/books/cultural_49/index.html",
            "https://books.toscrape.com/catalogue/category/books/erotica_50/index.html",
            "https://books.toscrape.com/catalogue/category/books/crime_51/index.html",       
        ]
        urls = ["https://www.amazon.in/" for _ in range(30)]
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
    asyncio.run(crawl_grid.launch_grid(instances=2))

    # 3. Add 4 more tabs (Total 6 tabs)
    asyncio.run(crawl_grid.distribute_tabs(tab_per_browser=2))
    
    # 4. Run 10 URL requests (Should see 6 successes and 4 failures)
    asyncio.run(crawl_grid.test_get_url())

    asyncio.run(crawl_grid.close_grid())

    tt = time.time() - st
    print(f"Total time: {tt}")