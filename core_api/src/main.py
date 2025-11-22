from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .healthcheck.routes import router as health_router
from .twilio_stream.routes import router as twilio_stream_router

app = FastAPI()

origins = [
    "http://localhost:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router, prefix="/health")
app.include_router(twilio_stream_router)
