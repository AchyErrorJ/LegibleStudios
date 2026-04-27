"""Health check and logging endpoints"""

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from datetime import datetime
from queue import Queue
import json
import asyncio

router = APIRouter()

# Global log queue
log_queue = Queue(maxsize=100)

class LogStreamer:
    """Helper class to broadcast logs"""
    
    @staticmethod
    def log(message: str, level: str = "info"):
        """Add a log entry to the stream"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "message": message,
            "level": level,
            "timestamp": timestamp
        }
        try:
            if not log_queue.full():
                log_queue.put(log_entry)
        except:
            pass
        print(f"[{level.upper()}] {message}")

@router.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "status": "running",
        "service": "Revit MCP Server"
    }

@router.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "endpoints": ["/", "/health", "/log-stream", "/internal-log", "/chat"]
    }

@router.post("/internal-log")
async def internal_log(request: dict):
    """Receive logs from Revit add-in"""
    try:
        message = request.get("message", "")
        level = request.get("level", "info")
        print(f"[REVIT {level.upper()}] {message}")
        return {"status": "ok"}
    except Exception as e:
        print(f"Error logging: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/log-stream")
async def log_stream():
    """SSE endpoint for streaming logs to frontend"""
    async def event_generator():
        try:
            while True:
                try:
                    if not log_queue.empty():
                        log_msg = log_queue.get_nowait()
                        yield {
                            "event": "log",
                            "data": json.dumps(log_msg)
                        }
                    else:
                        # Send keepalive
                        yield {
                            "event": "keepalive",
                            "data": json.dumps({"timestamp": datetime.now().isoformat()})
                        }
                except Exception as e:
                    print(f"Log stream error: {e}")
                
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Log stream connection closed")
            pass
    
    return EventSourceResponse(event_generator(), media_type="text/event-stream")
