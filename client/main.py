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


manager = BrowserManager()
app = FastAPI()

# @app.on_event("startup")
# async def startup_event():
#     """This runs once when you start the uvicorn server"""
#     manager.cleanup_all_resources()

@app.get('/launch/{port}')
async def launch_with_port(port: int):
    result = manager.launch(port=port)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result)
    return result

@app.get('/launch-tabs/{tabs}')
async def launch_tabs(tabs: int):
    result = manager.launch_tabs(total_tabs_to_add=tabs)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result)
    return result

@app.get('/kill/{port}')
async def kill_with_port(port: int):
    result = manager.kill(port)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result

@app.get('/list-browsers')
async def list_browsers():
    return manager.get_active_ports()

@app.get('/registry')
async def show_registry():
    return manager._load_registry()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host='localhost', port=8000, reload=True)
