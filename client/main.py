import os
import json
from fastapi import FastAPI, HTTPException
from DrissionPage import ChromiumPage, ChromiumOptions
import uvicorn

app = FastAPI()
REGISTRY_FILE = "browser_registry.json"


class BrowserManager:
    def __init__(self):
        if not os.path.exists(REGISTRY_FILE):
            self.save_registry({})

    def launch_browser(self, port):
        self.co = ChromiumOptions()
        self.co.set_local_port(port)
        self.browser = ChromiumPage(self.co)
        self.tab = self.browser.latest_tab

    def kill_browser(self):
        self.browser.quit()

    def get_registry(self):
        with open(REGISTRY_FILE, 'r') as f:
            return json.load(f)

    def save_registry(self, data):
        with open(REGISTRY_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    def update_status(self, port, status):
        data = self.get_registry()
        if status == "closed":
            if str(port) in data:
                del data[str(port)]
        else:
            data[str(port)] = {"status": status}
        self.save_registry(data)

manager = BrowserManager()

@app.get('/launch-browser/{port}')
async def launch_browser(port: int):
    try:
        manager.launch_browser(port)
        # Track in JSON
        manager.update_status(port, "available")

        return {
            "status": "success",
            "port": port,
            "tab_id": ''
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/list-browsers')
async def list_browsers():
    return manager.get_registry()


@app.get('/kill-browser/{port}')
async def kill_browser(port: int):
    try:
        manager.kill_browser()

        # Remove from JSON
        manager.update_status(port, "closed")
        return {"status": "success", "message": f"Browser on port {port} killed"}
    except Exception as e:
        # If the browser was already closed manually, update registry anyway
        manager.update_status(port, "closed")
        return {"status": "partial_success", "message": "Browser was not running, registry cleaned."}


if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=8000)