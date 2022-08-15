import os

import uvicorn
from aioprometheus.asgi.middleware import MetricsMiddleware
from aioprometheus.asgi.starlette import metrics
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sse_starlette import EventSourceResponse

import _employee_router
import _unit_router
import _workbench_router
from _logging import HANDLERS
from feecc_workbench.database import MongoDbWrapper
from feecc_workbench.Messenger import MessageLevels, message_generator, messenger
from feecc_workbench.models import GenericResponse
from feecc_workbench.utils import check_service_connectivity
from feecc_workbench.WorkBench import WorkBench

# apply logging configuration
logger.configure(handlers=HANDLERS)

# create app
app = FastAPI(title="Feecc Workbench daemon")

# include routers
app.include_router(_employee_router.router)
app.include_router(_unit_router.router)
app.include_router(_workbench_router.router)

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


@app.on_event("startup")
def startup_event() -> None:
    check_service_connectivity()
    MongoDbWrapper()
    app_version = os.getenv("VERSION", "Unknown")
    logger.info(f"Runtime app version: {app_version}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await WorkBench().shutdown()
    MongoDbWrapper().close_connection()


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
