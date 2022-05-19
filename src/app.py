import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

import _employee_router
import _unit_router
import _workbench_router
from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from feecc_workbench.WorkBench import WorkBench
from feecc_workbench.database import MongoDbWrapper

# apply logging configuration
logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

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


@app.on_event("startup")
def startup_event() -> None:
    MongoDbWrapper()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await WorkBench().shutdown()
    MongoDbWrapper().close_connection()


if __name__ == "__main__":
    uvicorn.run("app:app", port=5000)
