import os
from typing import Optional, List
from DrissionPage import ChromiumPage, ChromiumOptions
from utils import load_registry, save_registry, is_process_running, kill_process_tree

class BrowserManager:
    def __init__(self):
        self.MAX_BROWSERS = 10  # Hard limit
        self.MAX_TABS_PER_BROWSER = 10
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

    def launch_tabs(self, total_tabs_to_add: int) -> dict:
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
                        current_tabs[new_tab.tab_id] = {"status": "idle", "url": "about:blank"}
                        registry[port_str]["tabs"] = current_tabs
                        remaining -= 1
                        added_any = True
                        report[port_str] = report.get(port_str, 0) + 1
                
                if not added_any: break

            save_registry(registry)
            return {"status": "success", "distribution": report, "remaining": remaining}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def cleanup_all_resources(self):
        """Kills all processes listed in the registry."""
        registry = load_registry()
        for port, data in registry.items():
            kill_process_tree(data["process_id"])
        save_registry({})