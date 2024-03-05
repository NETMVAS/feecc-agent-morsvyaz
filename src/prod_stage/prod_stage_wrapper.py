from pymongo import InsertOne, UpdateOne
from dataclasses import asdict
from loguru import logger

from ..database.database import base_mongodb_wrapper
from ..feecc_workbench.Types import BulkWriteTask
from ..prod_stage.ProductionStage import ProductionStage

class ProdStageWrapper:
    collection = "productionStagesData"

    def _bulk_push_production_stages(self, production_stages: list[ProductionStage]) -> None:
        tasks: list[BulkWriteTask] = []

        for stage in production_stages:
            stage_dict = asdict(stage)
            del stage_dict["is_in_db"]

            if stage.is_in_db:
                task: BulkWriteTask = UpdateOne({"id": stage.id}, {"$set": stage_dict})
            else:
                task = InsertOne(stage_dict)
                stage.is_in_db = True

            tasks.append(task)

        result = base_mongodb_wrapper.bulk_write(self.collection, tasks)
        logger.debug(f"Bulk write operation result: {result.bulk_api_result}")


prod_stage_wrapper = ProdStageWrapper()