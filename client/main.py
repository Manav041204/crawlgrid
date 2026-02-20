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

@app.get('/launch/{port}')
async def launch_with_port(port: int):
    result = manager.launch(port=port)
    if result["status"] == "error":
        # If it's a limit issue, return 429 Forbidden
        if "limit" in result["message"]:
            raise HTTPException(status_code=429, detail=result["message"])
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@app.get('/launch-tabs/{tabs}')
async def launch_tabs(tabs: int):
    result = await manager.launch_tabs(total_tabs_to_add=tabs)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result)
    return result

@app.get('/kill/{port}')
async def kill_with_port(port: int):
    result = manager.kill(port)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result

@app.post('/get-url')
async def get_url(url: str):
    result = await manager.get_url(url)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result

# FOR BROWSER MANAGMENT

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
