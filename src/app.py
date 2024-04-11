import os

import uvicorn
from aioprometheus.asgi.middleware import MetricsMiddleware
from aioprometheus.asgi.starlette import metrics
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sse_starlette import EventSourceResponse
from contextlib import asynccontextmanager

from src.routers import employee_router, unit_router, workbench_router
from src._logging import HANDLERS
from src.database.database import BaseMongoDbWrapper
from src.feecc_workbench.Messenger import MessageLevels, message_generator, messenger
from src.database.models import GenericResponse
from src.feecc_workbench.utils import check_service_connectivity
from src.feecc_workbench.WorkBench import Workbench

# apply logging configuration
logger.configure(handlers=HANDLERS)


# create lifespan function for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    check_service_connectivity()
    app_version = os.getenv("VERSION", "Unknown")
    logger.info(f"Runtime app version: {app_version}")

    yield

    await Workbench.shutdown()
    BaseMongoDbWrapper.close_connection()


# create app
app = FastAPI(title="Feecc Workbench daemon", lifespan=lifespan)

# include routers
app.include_router(employee_router)
app.include_router(unit_router)
app.include_router(workbench_router)

# set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable Prometheus metrics
app.add_middleware(MetricsMiddleware)
app.add_route("/metrics", metrics)


@app.get("/notifications", tags=["notifications"])
async def stream_notifications() -> EventSourceResponse:
    """Stream backend emitted notifications into an SSE stream"""
    stream = message_generator()
    return EventSourceResponse(stream)


@app.post("/notifications", tags=["notifications"])
async def emit_notification(level: MessageLevels, message: str) -> GenericResponse:
    """Emit notification into an SSE stream"""
    await messenger.emit_message(level, message)
    return GenericResponse(status_code=status.HTTP_200_OK, detail="Notification emitted")


if __name__ == "__main__":
    uvicorn.run("app:app", port=5000)
