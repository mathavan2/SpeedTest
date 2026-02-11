from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import time
import os
import asyncio
import statistics

app = FastAPI()

# -------------------- CORS --------------------
# Dev-friendly (lock down origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- CONSTANTS --------------------
CHUNK_SIZE = 64 * 1024          # 64 KB
DOWNLOAD_DURATION = 20          # seconds
STREAM_DELAY = 0.001            # smooth LAN bursts


# -------------------- ROOT --------------------
@app.get("/")
def root():
    return {"status": "Speed Test Backend Running"}


# -------------------- DOWNLOAD --------------------
@app.get("/download")
async def download():
    def generator():
        start = time.time()
        while time.time() - start < DOWNLOAD_DURATION:
            yield os.urandom(CHUNK_SIZE)
            time.sleep(STREAM_DELAY)

    return StreamingResponse(
        generator(),
        media_type="application/octet-stream"
    )


# -------------------- UPLOAD --------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    total_bytes = 0
    start = time.time()

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)

    duration = time.time() - start

    if duration <= 0:
        return {"speed_mbps": 0}

    speed_mbps = (total_bytes * 8) / duration / 1_000_000
    return {
        "uploaded_mb": round(total_bytes / 1_000_000, 2),
        "speed_mbps": round(speed_mbps, 2),
    }


# -------------------- WEBSOCKET (PING + JITTER) --------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    latencies = []

    try:
        while True:
            # Send ping
            start = time.perf_counter()
            await ws.send_text("ping")

            # Wait for pong
            msg = await ws.receive_text()
            if msg != "pong":
                continue

            end = time.perf_counter()
            latency = (end - start) * 1000  # ms
            latencies.append(latency)

            # Calculate jitter (std deviation)
            jitter = (
                statistics.stdev(latencies)
                if len(latencies) > 1
                else 0
            )

            await ws.send_json({
                "ping": round(latency, 1),
                "jitter": round(jitter, 1)
            })

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("WebSocket disconnected")

    except Exception as e:
        print("WebSocket error:", e)

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "status": "ok",
        "service": "SpeedTest Backend",
        "uptime": "alive"
    }


