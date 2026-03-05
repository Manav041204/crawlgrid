import os
import json
from fastapi import FastAPI, HTTPException, Query
from DrissionPage import ChromiumPage, ChromiumOptions
import uvicorn
from typing import Optional
import psutil
from DrissionPage import ChromiumPage, ChromiumOptions
from typing import Optional, List

# Python file imports
from manage import BrowserManager
from utils import get_active_ports, load_registry, cleanup_all_resources


manager = BrowserManager()
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """This runs once when you start the uvicorn server"""
    cleanup_all_resources()

# FOR BROWSER EVENTS

@app.get('/launch')
async def launch_with_port(port: int):
    result = manager.launch(port=port)
    if result["status"] == "error":
        # If it's a limit issue, return 429 Forbidden
        if "limit" in result["message"]:
            raise HTTPException(status_code=429, detail=result["message"])
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@app.get('/launch-tabs')
async def launch_tabs(
    total_tabs: Optional[int] = None,
    tab_per_browser: Optional[int] = None
):
    if total_tabs:
        result = await manager.launch_tabs(total_tabs_to_add=total_tabs)
    else:
        result = await manager.launch_tabs(tab_per_browser=tab_per_browser)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result)
    return result

@app.get('/kill')
async def kill_with_port(port: int):
    result = manager.kill(port)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result

@app.post('/get-url')
async def get_url(url: str, release_tab: bool = True):
    result = await manager.get_url(url, release_tab)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result

@app.post('/release-tab')
async def release_tab(tab_id: str):
    result = await manager.release_tab_by_id(tab_id)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result

@app.post('/get-element')
async def get_element(tab_id: str, xpath: str, click: bool = False, input_text: str = None, timeout: int = 10):
    result = await manager.get_element(tab_id, xpath, click, input_text, timeout)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result

@app.get('/list-browsers')
async def list_browsers():
    return get_active_ports()

@app.get('/registry')
async def show_registry():
    return load_registry()

@app.get('/status')
async def get_node_status():
    """Quick overview of capacity."""
    registry = load_registry()
    browser_count = len(registry)
    total_tabs = sum(len(data.get("tabs", {})) for data in registry.values())
    
    return {
        "browsers": f"{browser_count}/{manager.MAX_BROWSERS}",
        "total_tabs": total_tabs,
        "available_slots": manager.MAX_BROWSERS - browser_count
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host='localhost', port=8000)
