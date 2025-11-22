from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .healthcheck.routes import router as health_router

app = FastAPI()

origins = [
    "http://localhost:8080",
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


app.include_router(health_router)
