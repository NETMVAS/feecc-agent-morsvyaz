from __future__ import annotations

import datetime as dt

from functools import reduce
from operator import add
from typing import no_type_check
from uuid import uuid4
from loguru import logger
from functools import lru_cache

from src.unit.unit_wrapper import UnitWrapper
from src.employee.Employee import Employee
from src.feecc_workbench.Messenger import messenger
from src.feecc_workbench.metrics import metrics
from src.database.models import ProductionSchema, AdditionalDetail
from src.prod_stage.ProductionStage import ProductionStage
from src.prod_schema.prod_schema_wrapper import ProdSchemaWrapper
from src.feecc_workbench.translation import translation
from src.feecc_workbench.Types import AdditionalInfo
from src.unit.unit_utils import Unit, UnitStatus
from src.feecc_workbench.utils import TIMESTAMP_FORMAT, timestamp


class UnitManager:
    """UnitManager class manages unit instances in the database."""
    collection = "unitData"

    def __init__(
        self,
        unit_id: str = "",
        schema: ProductionSchema = None,
        operation_name: str = "simple",
        components_units: list[Unit] = None,
        status: UnitStatus | str = UnitStatus.production,
    ) -> None:
        if unit_id:
            self.unit_id = unit_id
        else:
            self.unit_id = self.init_empty_unit(schema, operation_name, components_units, status)

    def init_empty_unit(
            self,
            schema: ProductionSchema,
            operation_name: str,
            components_units: list[Unit] = None,
            status: UnitStatus | str = UnitStatus.production,
        ) -> str:
        """Creates an empty unit instance in the database"""
        unit = Unit(status=status, schema_id=schema.schema_id, operation_name=operation_name, components_ids=[component.uuid for component in components_units])
        UnitWrapper.push_unit(unit)
        return unit.uuid
    
    def _set_component_slots(self, schema_id: str, component: Unit) -> None:
        """Update the _component_slots field"""
        field_name = f"_component_slots.{schema_id}"
        field_val = component
        UnitWrapper.update_by_uuid(self.unit_id, field_name, field_val)

    def _set_components_units(self, component: Unit) -> None:
        cur_components = self.components_units.append(component)
        UnitWrapper.update_by_uuid(self.unit_id, "components_units", cur_components)

    def get_unit_by_uuid(self, unit_id: str):
        return UnitWrapper.get_unit_by_uuid(unit_id)

    # @lru_cache(maxsize=4) ПОЧЕКАТЬ КАК КЕШИРОВАТЬ ЗАПРОС В МОНГУ (МБ С ИНДЕКСАМИ)
    @property
    def _get_cur_unit(self) -> Unit:
        if self.unit_id is None:
            raise ValueError("Unit id not found.")
        return UnitWrapper.get_unit_by_uuid(self.unit_id)

    @property
    def schema(self) -> ProductionSchema:
        return ProdSchemaWrapper.get_schema_by_id(self._get_cur_unit.schema_id)
    
    @property
    def internal_id(self) -> str:
        return self._get_cur_unit.internal_id
    
    @property
    def status(self) -> UnitStatus | str:
        return self._get_cur_unit.status
    
    @property
    def operation_stages(self) -> list[ProductionStage]:
        return self._get_cur_unit.operation_stages

    @property
    def components_schema_ids(self) -> list[str]:
        schema_id = self._get_cur_unit.schema_id
        schema = ProdSchemaWrapper.get_schema_by_id(schema_id)
        return schema.components_schema_ids or []

    @property
    def components_internal_ids(self) -> list[str]:
        return [c.internal_id for c in self.components_units]

    @property
    def model_name(self) -> str:
        return self._get_cur_unit.unit_name

    @property
    def components_units(self) -> list[Unit]:
        return UnitWrapper.get_components_units(self._get_cur_unit.components_ids)

    @property
    def components_filled(self) -> bool:
        return None not in self._get_cur_unit._component_slots.values()

    @property
    def next_pending_operation(self) -> ProductionStage | None:
        """get next pending operation if any"""
        return next((operation for operation in self._get_cur_unit.operation_stages if not operation.completed), None)
    
    @property
    def total_assembly_time(self) -> dt.timedelta:
        """calculate total time spent during all production stages"""

        def stage_len(stage: ProductionStage) -> dt.timedelta:
            if stage.session_start_time is None:
                return dt.timedelta(0)

            start_time: dt.datetime = dt.datetime.strptime(stage.session_start_time, TIMESTAMP_FORMAT)
            end_time: dt.datetime = (
                dt.datetime.strptime(stage.session_end_time, TIMESTAMP_FORMAT)
                if stage.session_end_time is not None
                else dt.datetime.now()
            )
            return end_time - start_time

        return reduce(add, (stage_len(stage) for stage in self._get_cur_unit.operation_stages)) if self._get_cur_unit.operation_stages else dt.timedelta(0)
    
    @no_type_check
    def assigned_components(self) -> dict[str, str | None] | None:
        """get a mapping for all the currently assigned components VS the desired components"""
        assigned_components = {component.schema_id: component.internal_id for component in self.components_units}

        for component_name in self.components_schema_ids:
            if component_name not in assigned_components:
                assigned_components[component_name] = None

        return assigned_components or None
    
    def assign_component(self, component: Unit) -> None:
        """Assign one of the composite unit's components to the unit"""
        if self.components_filled:
            messenger.warning(translation("NecessaryComponents"))
            raise ValueError(f"Unit {self.model_name} component requirements have already been satisfied")

        if component.schema_id not in self._get_cur_unit._component_slots:
            messenger.warning(
                translation("Component")
                + " "
                + component.model_name
                + " "
                + translation("NotPartOfUnit")
                + " "
                + self.model_name
            )
            raise ValueError(
                f"Cannot assign component {component.model_name} to {self.model_name} as it's not a component of it"
            )

        if self._get_cur_unit._component_slots.get(component.schema_id, "") is not None:
            messenger.warning(translation("Component") + " " + component.model_name + " " + translation("AlreadyAdded"))
            raise ValueError(
                f"Component {component.model_name} is already assigned to a composite Unit {self.model_name}"
            )

        if component.status is not UnitStatus.built:
            messenger.warning(
                translation("ComponentAssembly") + " " + component.model_name + " " + translation("NotCompleted")
            )
            raise ValueError(f"Component {component.model_name} assembly is not completed. {component.status=}")

        if component.featured_in_int_id is not None:
            messenger.warning(
                translation("ComponentN")
                + " "
                + component.internal_id
                + " "
                + translation("AlreadyUsed")
                + " "
                + component.featured_in_int_id
            )
            raise ValueError(
                f"Component {component.model_name} has already been used in unit {component.featured_in_int_id}"
            )

        self._set_component_slots(component.schema_id, component)
        self._set_components_units(component)
        component.featured_in_int_id = self._get_cur_unit.internal_id
        logger.info(f"Component {component.model_name} has been assigned to a composite Unit {self.model_name}")
        messenger.success(
            f"{translation('Component')} \
{component.model_name} {translation('AssignedToUnit')} \
{self.model_name}"
        )

    def start_operation(self, employee: Employee, additional_info: AdditionalInfo | None = None) -> None:
        """begin the provided operation and save data about it"""
        operation = self.next_pending_operation
        assert operation is not None, f"Unit {self.unit_id} has no pending operations ({self._get_cur_unit.status=})"
        operation.session_start_time = timestamp()
        operation.stage_data = additional_info
        operation.employee_name = employee.passport_code
        self._get_cur_unit.operation_stages[operation.number] = operation
        logger.debug(f"Started production stage {operation.name} for unit {self.unit_id}")

    def _duplicate_current_operation(self) -> None:
        cur_stage = self.next_pending_operation
        assert cur_stage is not None, "No pending stages to duplicate"
        target_pos = cur_stage.number + 1
        dup_operation = ProductionStage(
            name=cur_stage.name,
            parent_unit_uuid=cur_stage.parent_unit_uuid,
            number=target_pos,
        )
        updated_bio = self._get_cur_unit.operation_stages.insert(target_pos, dup_operation)

        for i in range(target_pos + 1, len(updated_bio)):
            updated_bio[i].number += 1

        UnitWrapper.update_by_uuid(self.unit_id, "operation_stages", updated_bio)

    async def end_operation(
        self,
        video_hashes: list[str] | None = None,
        additional_info: AdditionalInfo | None = None,
        premature: bool = False,
        override_timestamp: str | None = None,
    ) -> None:
        """
        wrap up the session when video recording stops and save video data
        as well as session end timestamp
        """
        operation = self.next_pending_operation
        bio = self._get_cur_unit.operation_stages

        if operation is None:
            raise ValueError("No pending operations found")

        logger.info(f"Ending production stage {operation.name} on unit {self.unit_id}")
        operation.session_end_time = override_timestamp or timestamp()

        if premature:
            self._duplicate_current_operation()
            operation.name += " " + translation("Unfinished")
            operation.ended_prematurely = True

        if video_hashes:
            UnitWrapper.update_by_uuid(self.unit_id, "certificate_txn_hash", video_hashes)

        if operation.stage_data is not None:
            operation.stage_data = {
                **operation.stage_data,
                **(additional_info or {}),
                "detail": self._get_cur_unit.detail.to_json(),
            }

        operation.completed = True
        bio[operation.number] = operation

        if all(stage.completed for stage in bio):
            prev_status = self._get_cur_unit.status
            UnitWrapper.update_by_uuid(self.unit_id, "status", UnitStatus.built)
            logger.info(
                f"Unit has no more pending production stages. Unit status changed: {prev_status} -> "
                f"{UnitStatus.built}"
            )
            metrics.register_complete_unit(None, self)

        self.employee = None


        