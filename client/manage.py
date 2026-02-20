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

        pid = registry[port_str]["process_id"]
        success = kill_process_tree(pid)
        
        del registry[port_str]
        save_registry(registry)
        
        return {"status": "success", "message": f"Port {port} terminated." if success else "Process already dead."}

    async def launch_tabs(self, total_tabs_to_add: int) -> dict:
        # Distribution logic remains here as it's a core 'Management' feature
        try:
            registry = load_registry()
            active_ports = list(registry.keys())
            if not active_ports:
                return {"status": "error", "message": "No active browsers."}

            remaining = total_tabs_to_add
            report = {}

            while remaining > 0:
                added_any = False
                for port_str in active_ports:
                    if remaining <= 0: break
                    
                    page = self.get_browser(int(port_str))
                    current_tabs = registry[port_str].get("tabs", {})
                    
                    if len(current_tabs) < self.MAX_TABS_PER_BROWSER:
                        new_tab = page.new_tab()

                        await self.tab_pool.put({"port": port_str, "obj": new_tab})

                        current_tabs[new_tab.tab_id] = {"status": "idle", "url": "about:blank"}
                        registry[port_str]["tabs"] = current_tabs
                        remaining -= 1
                        added_any = True
                        report[port_str] = report.get(port_str, 0) + 1
                
                if not added_any: break

            save_registry(registry)
            return {"status": "success", "message": "Distribution Success", "distribution": report, "remaining": remaining}
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
                # You can set a timeout here to prevent one slow site from hanging the tab
                tab_obj.get(url, timeout=20)

            print(f"🚀 [Grid] Assigning {url} to Port {port} | Tab {tab_id}")
            await asyncio.to_thread(perform_navigation)

            # 3. Update Status (Background/Optional)
            update_registry(port, tab_id, "busy", url)
            
            return {
                "status": "success",
                "port": port,
                "tab_id": tab_id,
                "url": url,
                "message": f"Navigation complete on Port {port}"
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