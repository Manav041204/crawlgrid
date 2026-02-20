import os
import json
import psutil

REGISTRY_FILE = "browser_registry.json"

def load_registry() -> dict:
    """Read the registry from disk."""
    try:
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, 'r') as f:
                return json.load(f)
        return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_registry(data: dict):
    """Write the registry to disk."""
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(data, f, indent=4)


def update_registry(port: str, tab_id: str, status: str, url: str):
    """Helper to sync in-memory state to the JSON registry."""
    try:
        registry = load_registry()
        print("$$$$", type(port), tab_id)
        if port in registry and tab_id in registry[port]["tabs"]:
            registry[port]["tabs"][tab_id]["status"] = status
            registry[port]["tabs"][tab_id]["url"] = url
            print(f"✅ Registry Sync: {port} | {tab_id} -> {url}")
            save_registry(registry)
        
    except Exception as e:
        print(f"⚠️ Registry Sync Warning: {e}")


def get_active_ports():
    registry = load_registry()
    # Returns a list of keys (ports) as integers
    return [int(p) for p in registry.keys()]

def is_process_running(pid: int) -> bool:
    """Check if a PID exists and is active."""
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
        return False

def kill_process_tree(pid: int):
    """Hard kill a process and all its children."""
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
        return True
    except psutil.NoSuchProcess:
        return False

def cleanup_all_resources():
        """Kills all processes listed in the registry."""
        registry = load_registry()
        for port, data in registry.items():
            kill_process_tree(data["process_id"])
        save_registry({})
