from typing import Optional
import os
import json
from DrissionPage import ChromiumPage, ChromiumOptions
import psutil

REGISTRY_FILE = "browser_registry.json"

class BrowserManager:
    def __init__(self):
        self._ensure_registry_exists()

    def _ensure_registry_exists(self):
        if not os.path.exists("REGISTRY_FILE"):
            self._save_registry({})

    def _load_registry(self) -> dict:
        try:
            with open(REGISTRY_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_registry(self, data: dict):
        with open(REGISTRY_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    def launch(self, port: Optional[int] = None) -> dict:
        try:
            co = ChromiumOptions()
            if port is None:
                co.set_local_port(port)
            
            # 1. Launch Browser
            page = ChromiumPage(co)
            actual_port = str(page.address.split(':')[-1])
            pid = page.process_id
            tab_ids = page.tab_ids
            
            # 2. Update Persistent Registry
            registry = self._load_registry()
            registry[actual_port] = {
                "process_id": pid,
                "tab_ids": tab_ids,
                "status": "running"
            }
            self._save_registry(registry)
            
            return {
                "status": "success",
                "port": int(actual_port),
                "process_id": pid,
                "tab_ids": tab_ids,
                "message": f"Browser started on port {actual_port}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Launch failed: {str(e)}"}
    
    def get_browser(self, port: int) -> ChromiumPage:
        """
        Retrieves a browser instance. If the process is crashed, 
        it heals itself by restarting the browser.
        """
        registry = self._load_registry()
        port_str = str(port)

        if port_str in registry:
            pid = registry[port_str].get("process_id")
            
            # Check if process is actually running
            if not self._is_process_running(pid):
                self.launch(port=port) # Re-launch on the same port
        
        # Now that we've ensured it's alive (or restarted), return the page object
        co = ChromiumOptions().set_local_port(port)
        return ChromiumPage(co)


    def _is_process_running(self, pid: int) -> bool:
        """Checks if a PID exists and is a python/chrome process."""
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            return False


    def kill(self, port: int) -> dict:
        registry = self._load_registry()
        port_str = str(port)

        if port_str not in registry:
            return {"status": "error", "message": f"Port {port} not found in registry."}

        pid = registry[port_str]["process_id"]
        
        try:
            # Hard kill the process tree
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            
            kill_msg = f"Process {pid} killed."
        except psutil.NoSuchProcess:
            kill_msg = "Process already dead."
        except Exception as e:
            return {"status": "error", "message": f"Kill failed: {str(e)}"}

        # Clean up registry
        del registry[port_str]
        self._save_registry(registry)
        
        return {
            "status": "success",
            "port": port,
            "message": f"{kill_msg} Registry updated."
        }
    
    def launch_tabs(self, total_tabs_to_add: int) -> dict:
        try:
            registry = self._load_registry()
            active_ports = list(registry.keys())
            
            if not active_ports:
                return {"status": "error", "message": "No active browsers found to distribute tabs."}

            distribution_report = {}
            remaining_tabs = total_tabs_to_add

            while remaining_tabs > 0:
                added_in_this_round = 0
                
                for port_str in active_ports:
                    if remaining_tabs <= 0:
                        break
                    
                    page = self.get_browser(int(port_str))
                    
                    current_tab_count = len(page.tab_ids)
                    
                    if current_tab_count < 10:
                        page.new_tab()
                        remaining_tabs -= 1
                        added_in_this_round += 1
                        
                        registry[port_str]["tab_ids"] = page.tab_ids

                        distribution_report[port_str] = distribution_report.get(port_str, 0) + 1
                    
                if added_in_this_round == 0:
                    break

            self._save_registry(registry)

            if remaining_tabs > 0:
                message = f"Distributed {total_tabs_to_add - remaining_tabs} tabs. {remaining_tabs} tabs could not be opened (Hard limit of 10 reached on all browsers)."
            else:
                message = f"Successfully distributed {total_tabs_to_add} tabs across all browsers."

            return {
                "status": "success",
                "distribution": distribution_report,
                "remaining_unopened": remaining_tabs,
                "message": message
            }

        except Exception as e:
            return {"status": "error", "message": f"Tab Launch failed: {str(e)}"}

    def get_active_ports(self):
        registry = self._load_registry()
        # Returns a list of keys (ports) as integers
        return [int(p) for p in registry.keys()]
    
    def cleanup_all_resources(self):
        """Kills all processes listed in the registry."""
        registry = self._load_registry()
        ports = list(registry.keys())
        
        if not ports:
            print("Registry empty. No resources to clean up.")
            return

        print(f"Found {len(ports)} active browser instances. Cleaning up...")
        
        for port in ports:
            try:
                pid = registry[port]["process_id"]
                
                # Kill process tree
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
                
                print(f"Killed process {pid} (Port {port})")
                
            except psutil.NoSuchProcess:
                print(f"Process {pid} (Port {port}) already dead.")
            except Exception as e:
                print(f"Error killing process {pid}: {e}")
        
        # Clear registry
        self._save_registry({})