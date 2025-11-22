from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .healthcheck.routes import router as health_router
from .routes.simulation import router as simulation_router
from .twilio_stream.routes import router as twilio_stream_router

app = FastAPI(
    title="TIQN Emergency Services Core",
    description="Core processing functions for emergency call transcription and data extraction",
    version="0.1.0",
)

origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    "https://tiqn.app",
    "https://www.tiqn.app",
    "https://api.tiqn.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)

app.include_router(health_router, prefix="/health")
app.include_router(twilio_stream_router)
app.include_router(simulation_router)
