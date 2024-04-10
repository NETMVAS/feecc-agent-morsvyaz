import pydantic

from src.feecc_workbench.utils import time_execution
from src.database.database import BaseMongoDbWrapper
from src.database.models import ProductionSchema


class _ProdSchemaWrapper:
    collection = "productionSchemas"

    @time_execution
    def get_all_schemas(self, position: str) -> list[ProductionSchema]:
        """get all production schemas"""
        query = {"allowed_positions": {"$in": [None, [], position]}}
        schema_data = BaseMongoDbWrapper.find(collection=self.collection, filters=query, projection={"_id": 0})
        return [ProductionSchema(**schema) for schema in schema_data]

    @time_execution
    def get_schema_by_id(self, schema_id: str) -> ProductionSchema:
        """get the specified production schema"""
        filters = {"schema_id": schema_id}
        projection = {"_id": 0}
        target_schema = BaseMongoDbWrapper.find_one(collection=self.collection, filters=filters, projection=projection)

        if target_schema is None:
            raise ValueError(f"Schema {schema_id} not found")

        return ProductionSchema(**target_schema)


ProdSchemaWrapper = _ProdSchemaWrapper()
