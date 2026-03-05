import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

# Shared state to control the stream
stop_event = asyncio.Event()

async def data_generator(request: Request):
    """
    Generates a continuous stream of data until stop_event is set
    or the client disconnects.
    """
    stop_event.clear()
    count = 0
    
    print("Stream started...")
    
    try:
        while not stop_event.is_set():
            # Check if client closed the connection (browser/curl)
            if await request.is_disconnected():
                print("Client disconnected.")
                break
                
            yield f"data: Sequence {count} - Stream is active\n\n"
            count += 1
            await asyncio.sleep(1) # Wait 1 second between chunks
            
        if stop_event.is_set():
            yield "data: [TERMINATED BY REMOTE STOP]\n\n"
            print("Stream stopped via /stop endpoint.")
            
    except asyncio.CancelledError:
        print("Stream task was cancelled.")

@app.get("/other-task")
async def other_task():
    return {"message": "I am a different endpoint. I won't stop the stream!"}

@app.get("/stream")
async def stream(request: Request):
    return StreamingResponse(
        data_generator(request), 
        media_type="text/event-stream"
    )

@app.get("/stop")
async def stop_stream():
    stop_event.set()
    return {"status": "success", "message": "Stop signal sent to all streams"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)