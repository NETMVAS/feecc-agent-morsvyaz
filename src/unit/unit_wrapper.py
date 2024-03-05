from loguru import logger

from ..database.database import base_mongodb_wrapper
from ..database._db_utils import _get_database_client, _get_unit_dict_data
from .Unit import Unit
from ..prod_stage.prod_stage_wrapper import prod_stage_wrapper


class UnitWrapper:
    collection = "unitData"
    
    def push_unit(self, unit: Unit, include_components: bool = True) -> None:
        """Upload or update data about the unit into the DB"""
        if unit.components_units and include_components:
            for component in unit.components_units:
                self.push_unit(component)

        prod_stage_wrapper._bulk_push_production_stages(unit.biography)
        unit_dict = _get_unit_dict_data(unit)

        if unit.is_in_db:
            filters = {"uuid": unit.uuid}
            update = {"$set": unit_dict}
            base_mongodb_wrapper.update(self.collection, update, filters)
        else:
            base_mongodb_wrapper.insert(self.collection, unit_dict)

    def unit_update_single_field(self, unit_internal_id: str, field_name: str, field_val: Any) -> None:
        self._unit_collection.find_one_and_update(
            {"internal_id": unit_internal_id}, {"$set": {field_name: field_val}}
        )
        logger.debug(f"Unit {unit_internal_id} field '{field_name}' has been set to '{field_val}'")