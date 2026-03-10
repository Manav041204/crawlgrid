import os
import asyncio
from typing import Optional, List
from DrissionPage import ChromiumPage, ChromiumOptions
from fastapi import Request
from fastapi.responses import StreamingResponse
import json
# Python file imports
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
        self.active_elements = {}
    
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
            return {"status": "success", "message": f"Port {port} terminated."}

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
                        tab_id = new_tab.tab_id
                        # Put into the LIVE memory pool
                        tab_data = {
                            "port": port_str, 
                            "obj": new_tab, 
                            "tab_id": tab_id
                        }
                        await self.tab_pool.put(tab_data)
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
    
    # async def launch_tabs(self, total_tabs: Optional[int] = None, tab_per_browser: Optional[int] = None) -> dict:
    #     try:
    #         registry = load_registry()
    #         active_ports = list(registry.keys())
    #         if not active_ports:
    #             return {"status": "error", "message": "No active browsers found."}

    #         report = {}
            
    #         for port_str in active_ports:
    #             page = self.get_browser(int(port_str))
                
    #             # 1. ACTUAL PHYSICAL CHECK: Talk to the browser process
    #             # We use .tab_ids because it is the source of truth
    #             actual_tab_ids = await asyncio.to_thread(lambda: page.tab_ids)
                
    #             # 2. RECONCILE MEMORY: Add any "unknown" physical tabs to our index
    #             for tid in actual_tab_ids:
    #                 if tid not in self.tab_index:
    #                     tab_obj = await asyncio.to_thread(page.get_tab, tid)
    #                     self.tab_index[tid] = {"port": port_str, "obj": tab_obj, "tab_id": tid}
    #                     await self.tab_pool.put(self.tab_index[tid])

    #             # 3. CALCULATE BASED ON TRUTH: 
    #             # Use actual_tab_ids count, not what the registry JSON said
    #             current_physical_count = len(actual_tab_ids)
    #             target = tab_per_browser if tab_per_browser else current_physical_count
    #             needed = max(0, target - current_physical_count)
                
    #             # 4. CREATE ONLY WHAT IS MISSING
    #             new_tab_data = {}
    #             for _ in range(needed):
    #                 new_tab = await asyncio.to_thread(page.new_tab)
    #                 tid = new_tab.tab_id
                    
    #                 # Store in memory
    #                 tab_info = {"port": port_str, "obj": new_tab, "tab_id": tid}
    #                 self.tab_index[tid] = tab_info
    #                 await self.tab_pool.put(tab_info)
                    
    #                 # Track for registry update
    #                 new_tab_data[tid] = {"status": "idle", "url": "about:blank"}
    #                 report[port_str] = report.get(port_str, 0) + 1

    #             # 5. SYNC REGISTRY: Overwrite registry with actual physical state
    #             # This wipes out any "ghost" tabs that were in the JSON but not in the browser
    #             current_tabs_registry = {}
    #             # Re-fetch physical IDs to be 100% sure
    #             final_ids = await asyncio.to_thread(lambda: page.tab_ids)
    #             for tid in final_ids:
    #                 current_tabs_registry[tid] = {"status": "idle", "url": "about:blank"}
                
    #             registry[port_str]["tabs"] = current_tabs_registry

    #         save_registry(registry)
            
    #         return {
    #             "status": "success", 
    #             "added": report,
    #             "total_pool": self.tab_pool.qsize()
    #         }

    #     except Exception as e:
    #         return {"status": "error", "message": f"Sync failed: {str(e)}"}

    async def get_url(self, url: str, release_tab: bool = True) -> dict:
        """Uses the in-memory tab pool for near-instant URL processing."""
        tab_data = None
        try:
            while True:
                # 1. Acquire: Wait for an idle tab from the memory queue
                # If the queue is empty, this will pause here without blocking the server
                tab_data = await self.tab_pool.get()
                
                # Check if tab was invalidated by a kill operation
                if tab_data["tab_id"] not in self.tab_index:
                    self.tab_pool.task_done()
                    tab_data = None
                    continue
                break

            tab_obj = tab_data["obj"]
            port = tab_data["port"]
            tab_id = tab_data["tab_id"]

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
            if tab_data is not None:
                if release_tab:
                    if tab_data["tab_id"] in self.tab_index:
                        # 4. Release: Crucial! Put the tab back into the pool so others can use it
                        await self.tab_pool.put(tab_data)
                        update_registry(tab_data["port"], tab_data["tab_id"], "idle", "about:blank")

                # Signal that the processing for this specific item is done
                self.tab_pool.task_done()

    async def get_element(self, tab_id: str, xpath: str, click: bool = False, input_text: str = None, timeout: int = 10):
        try:
            tab_data = self.tab_index.get(tab_id)
            
            if not tab_data:
                return {"status": "error", "message": f"Tab {tab_id} not found in pool."}
            
            tab_obj = tab_data["obj"]
            port = tab_data["port"]

            def perform_operation_element():
                element = tab_obj.ele(f"xpath:{xpath}", timeout=timeout)
                if element:
                    return element
                else:
                    return None

            def perform_operation_click(element):
                if element:
                    return element.click(timeout=timeout)
                else:
                    return None 

            def perform_operation_input(element):
                if element:
                    return element.input(input_text)
                    # return True
                else:
                    return None 

            element = await asyncio.to_thread(perform_operation_element)
            if not element:
                return {"status": "error", "message": "Element not found"}

            self.active_elements[tab_id]= element

            if click:
                is_clicked = await asyncio.to_thread(perform_operation_click, element)
                if not is_clicked:
                    return {"status": "error", "message": "Element not clicked"}

            if input_text:
                is_input = await asyncio.to_thread(perform_operation_input, element)
                if not is_input:
                    return {"status": "error", "message": "Element not input"}

            return {
                "status": "success",
                "port": port,
                "tab_id": tab_id,
                "element_html": element.html,
                "message": f"Element found and clicked on tab_id {tab_id} Port {port}" if click else f"Element found on tab_id {tab_id} Port {port}"
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def listen_generator(self, request: Request, tab_id: str, targets: Optional[str] = None):
        tab_data = self.tab_index.get(tab_id)
        if not tab_data:
            yield "data: {\"status\": \"error\", \"message\": \"Tab not found\"}\n\n"
            return

        tab_obj = tab_data["obj"]
        stream_id = f"listen_{tab_id}"
        self.active_elements[stream_id] = True 
        
        # Filter traffic for specific targets if provided
        tab_obj.listen.start(targets=targets) 

        try:
            while self.active_elements.get(stream_id):
                if await request.is_disconnected():
                    break

                # Poll for packets without blocking the main loop
                res_packet = await asyncio.to_thread(tab_obj.listen.wait, timeout=1)

                if res_packet:
                    # Fetching body is a blocking network call in DrissionPage
                    raw_body = await asyncio.to_thread(lambda: res_packet.response.body if res_packet.response else None)
                    
                    # --- SAFE ENCODING BLOCK ---
                    # Convert bytes to a JSON-serializable format
                    body_str = None
                    if isinstance(raw_body, bytes):
                        try:
                            # Try decoding as text
                            body_str = raw_body.decode('utf-8')
                        except UnicodeDecodeError:
                            # If binary (images/compressed), use a placeholder or base64
                            body_str = f"<Binary Data: {len(raw_body)} bytes>"
                    elif raw_body is not None:
                        body_str = str(raw_body)
                    
                    packet_payload = {
                        "url": res_packet.url,
                        "method": res_packet.request.method,
                        "request_headers": dict(res_packet.request.headers),
                        "response_headers": dict(res_packet.response.headers) if res_packet.response else {},
                        "status": res_packet.response.status if res_packet.response else "pending",
                        "cookies": tab_obj.cookies().as_json(),
                        "body": body_str  # Now guaranteed to be a string or None
                    }

                    try:
                        # Ensure the dump itself doesn't crash the generator
                        yield f"data: {json.dumps(packet_payload)}\n\n"
                    except (TypeError, ValueError) as e:
                        yield f"data: {json.dumps({'error': 'serialization_failed', 'details': str(e)})}\n\n"
                
                # Small sleep to yield control back to the event loop
                await asyncio.sleep(0.05)

        except Exception as e:
            # Catch unexpected errors to prevent the ASGI worker from crashing
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        finally:
            # Ensure cleanup happens even if the client disconnects or an error occurs
            await asyncio.to_thread(tab_obj.listen.stop)
            self.active_elements.pop(stream_id, None)
            # Optional: Signal the client that the stream is closing gracefully
            # yield "data: [DONE]\n\n"

    async def take_screenshot(self, tab_id: str, name: str = "screenshot.png") -> Optional[str]:
        try:
            tab_data = self.tab_index.get(tab_id)
            if not tab_data:
                return None
            
            tab_obj = tab_data["obj"]
            
            # Execute the screenshot in a thread to keep the event loop free
            file_path = await asyncio.to_thread(
                lambda: tab_obj.get_screenshot(path=name, full_page=True)
            )
            return file_path
        except Exception as e:
            print(f"Screenshot Error: {e}")
            return None

    async def release_tab_by_id(self, tab_id: str) -> dict:
        try:
            if tab_id not in self.tab_index:
                return {"status": "error", "message": f"Tab {tab_id} not found."}
            
            tab_data = self.tab_index[tab_id]
            await self.tab_pool.put(tab_data)
            update_registry(tab_data["port"], tab_id, "idle", "about:blank")
            
            return {"status": "success", "message": f"Tab {tab_id} released."}
        except Exception as e:
            return {"status": "error", "message": str(e)}