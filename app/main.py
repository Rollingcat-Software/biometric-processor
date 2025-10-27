import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import face

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FIVUCSAS Biometric Processor",
    description="Face recognition and liveness detection service",
    version="1.0.0-MVP"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(face.router, prefix="/api/v1", tags=["Face Recognition"])


@app.get("/")
def read_root():
    return {
        "service": "FIVUCSAS Biometric Processor",
        "version": "1.0.0-MVP",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
