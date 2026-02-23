import os
import asyncio
from typing import Optional, List
from DrissionPage import ChromiumPage, ChromiumOptions
from utils import load_registry, save_registry, is_process_running, kill_process_tree, update_registry

class BrowserManager:
    def __init__(self):
        self.MAX_BROWSERS = 10  # Hard limit
        self.MAX_TABS_PER_BROWSER = 10
        self.tab_pool = asyncio.Queue()
        self.tab_index = {}
        # Ensure registry exists on init
        if not os.path.exists("browser_registry.json"):
            save_registry({})
    


    def launch(self, port: Optional[int] = None) -> dict:
        registry = load_registry()
        
        # 1. Check Browser Limit
        if len(registry) >= self.MAX_BROWSERS and str(port) not in registry:
            return {
                "status": "error", 
                "message": f"Browser limit reached ({self.MAX_BROWSERS}). Cannot launch more."
            }
        try:
            co = ChromiumOptions()
            if port is not None:
                co.set_local_port(port)
            
            page = ChromiumPage(co)
            actual_port = str(page.address.split(':')[-1])
            pid = page.process_id
            
            # Initialize tab dictionary
            tab_data = {tid: {"status": "idle", "url": "about:blank"} for tid in page.tab_ids}
            
            registry[actual_port] = {
                "process_id": pid,
                "tabs": tab_data,
                "status": "running"
            }
            save_registry(registry)
            
            return {
                "status": "success",
                "port": int(actual_port),
                "tab_ids": list(tab_data.keys())
            }
        except Exception as e:
            return {"status": "error", "message": f"Launch failed: {str(e)}"}

    def get_browser(self, port: int) -> ChromiumPage:
        registry = load_registry()
        port_str = str(port)

        if port_str in registry:
            pid = registry[port_str].get("process_id")
            if not is_process_running(pid):
                self.launch(port=port)
        
        return ChromiumPage(ChromiumOptions().set_local_port(port))

    def kill(self, port: int) -> dict:
        registry = load_registry()
        port_str = str(port)

        if port_str not in registry:
            return {"status": "error", "message": f"Port {port} not found."}

        if port_str in registry:
            # CLEANUP MAP: Remove all tabs belonging to this port
            tabs_to_remove = [tid for tid, data in self.tab_index.items() if data['port'] == port_str]
            for tid in tabs_to_remove:
                del self.tab_index[tid]
            
            # Kill process and registry as before...
            pid = registry[port_str]["process_id"]
            kill_process_tree(pid)
            del registry[port_str]
            save_registry(registry)
            return {"status": "success", "message": f"Port {port} terminated." if success else "Process already dead."}

    async def launch_tabs(self, total_tabs_to_add: int = 0, tab_per_browser: int = 0) -> dict:
        """
        Distributes tabs across active browsers.
        If tab_per_browser is set, it fills each browser to that specific amount.
        If total_tabs_to_add is set, it distributes that many tabs across the grid.
        """
        try:
            registry = load_registry()
            active_ports = list(registry.keys())
            if not active_ports:
                return {"status": "error", "message": "No active browsers."}

            # 1. Determine our goal
            # If user provides tab_per_browser, we ignore total_tabs_to_add and fill each browser
            using_per_browser_mode = tab_per_browser > 0
            remaining = total_tabs_to_add if not using_per_browser_mode else 9999 # Large number for while loop
            
            report = {}

            while remaining > 0:
                added_any = False
                for port_str in active_ports:
                    # Stop if we were doing total_tabs and reached the goal
                    if not using_per_browser_mode and remaining <= 0:
                        break
                    
                    page = self.get_browser(int(port_str))
                    current_tabs = registry[port_str].get("tabs", {})
                    current_count = len(current_tabs)

                    # 2. Check limits based on mode
                    if using_per_browser_mode:
                        can_add = current_count < tab_per_browser
                    else:
                        can_add = current_count < self.MAX_TABS_PER_BROWSER

                    if can_add:
                        # Physical creation
                        new_tab = page.new_tab()

                        # Put into the LIVE memory pool
                        await self.tab_pool.put({"port": port_str, "obj": new_tab, "tab_id": new_tab.tab_id})
                        self.tab_index[tab_id] = tab_data

                        # Update Registry data
                        current_tabs[new_tab.tab_id] = {"status": "idle", "url": "about:blank"}
                        registry[port_str]["tabs"] = current_tabs
                        
                        # Update counters
                        if not using_per_browser_mode:
                            remaining -= 1
                        
                        added_any = True
                        report[port_str] = report.get(port_str, 0) + 1
                
                # If a full loop through all browsers added nothing, we are at capacity
                if not added_any:
                    break
                
                # If using per-browser mode, we break once all browsers hit the target
                if using_per_browser_mode:
                    # Check if all active ports have reached tab_per_browser
                    all_filled = all(len(registry[p].get("tabs", {})) >= tab_per_browser for p in active_ports)
                    if all_filled:
                        break

            save_registry(registry)
            
            status_msg = f"Set browsers to {tab_per_browser} tabs each" if using_per_browser_mode else "Distribution Success"
            
            return {
                "status": "success", 
                "message": status_msg, 
                "distribution": report, 
                "total_in_pool": self.tab_pool.qsize()
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def get_url(self, url: str) -> dict:
        """Uses the in-memory tab pool for near-instant URL processing."""
        try:
            # 1. Acquire: Wait for an idle tab from the memory queue
            # If the queue is empty, this will pause here without blocking the server
            tab_data = await self.tab_pool.get()
            tab_obj = tab_data["obj"]
            port = tab_data["port"]
            tab_id = tab_obj.tab_id

            # 2. Work: Navigate in a separate thread
            # This prevents tab.get() from freezing your entire FastAPI application
            def perform_navigation():
                # Start listening for network traffic
                # target_urls allows us to filter specifically for the main request
                tab_obj.listen.start(targets=url)
                
                # Navigate
                tab_obj.get(url, timeout=5)
                
                # Catch the specific packet for the URL we requested
                res_packet = tab_obj.listen.wait(timeout=5)
                
                # Extract Data
                html = tab_obj.html
                cookies = tab_obj.cookies().as_json()
                
                if res_packet:
                    request_headers = dict(res_packet.request.headers)
                else:
                    request_headers = {}
                    
                # Stop listening to clear memory
                tab_obj.listen.stop()
                
                return html, request_headers, cookies

            print(f"🚀 [Grid] Assigning {url} to Port {port} | Tab {tab_id}")
            html, headers, cookies = await asyncio.to_thread(perform_navigation)

            # 3. Update Status (Background/Optional)
            update_registry(port, tab_id, "busy", url)
            
            return {
                "status": "success",
                "port": port,
                "tab_id": tab_id,
                "url": url,
                "message": f"Navigation complete on Port {port}",
                "html": html,
                "headers": headers,
                "cookies": cookies
            }

        except Exception as e:
            print(f"❌ [Grid] Error processing {url}: {e}")
            return {"status": "error", "message": str(e)}

        finally:
            # 4. Release: Crucial! Put the tab back into the pool so others can use it
            await self.tab_pool.put(tab_data)
            update_registry(port, tab_id, "idle", "about:blank")

            # Signal that the processing for this specific item is done
            self.tab_pool.task_done()

    async def get_element(self, tab_id: str, xpath: str, timeout: int = 10):
        try:
            tab_data = self.tab_index.get(tab_id)
            
            if not tab_data:
                return {"status": "error", "message": f"Tab {tab_id} not found in pool."}
            
            tab_obj = tab_data["obj"]
            port = tab_data["port"]

            def perform_operation():
                element = tab_obj.ele(f"xpath://{xpath}", timeout=timeout)
                if element:
                    return element
                else:
                    return None

            element = await asyncio.to_thread(perform_operation)
            
            if not element:
                return {"status": "error", "message": "Element not found"}

            return {
                "status": "success",
                "port": port,
                "tab_id": tab_id,
                "element": element,
                "message": f"Element found on Port {port}"
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}