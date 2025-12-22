from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import jobs

app = FastAPI(title="OfferClick API", version="1.0.0")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for LAN access (simpler for dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)

@app.get("/")
async def root():
    return {"message": "OfferClick API"}

@app.post("/shutdown")
async def shutdown():
    """Shutdown the server"""
    import os
    import threading
    import time
    
    def kill_server():
        time.sleep(1)
        os._exit(0)
        
    threading.Thread(target=kill_server).start()
    return {"message": "Shutting down..."}

