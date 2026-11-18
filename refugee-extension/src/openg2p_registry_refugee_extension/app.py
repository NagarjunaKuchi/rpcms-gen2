# ruff: noqa: E402
import asyncio
import logging

from .config import Settings

_config = Settings.get_config()

from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_fastapi_common.context import dbengine
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from openg2p_registry_core.app import Initializer as CoreInitializer

from .register_domain.models import (
    G2PRegisterIndividual,
    G2PRegisterHistoryIndividual,
    G2PIntakeFormIndividual,
    G2PRegisterIndividualDisability,
    G2PRegisterHistoryIndividualDisability,
    G2PIntakeFormIndividualDisability,
    G2PRegisterHousehold,
    G2PRegisterHistoryHousehold,
    G2PIntakeFormHousehold,
    G2PRegisterIndividualProgram,
    G2PRegisterHistoryIndividualProgram,
    G2PIntakeFormIndividualProgram,
    G2PRegisterAssistanceEvent,
    G2PRegisterHistoryAssistanceEvent,
    G2PIntakeFormAssistanceEvent,
    G2PRegisterIdRenewalRequest,
    G2PRegisterHistoryIdRenewalRequest,
    G2PIntakeFormIdRenewalRequest,
    G2PRegisterPartner,
    G2PRegisterHistoryPartner,
    G2PIntakeFormPartner,
    G2PRegisterProject,
    G2PRegisterHistoryProject,
    G2PIntakeFormProject,
    G2PRegisterProjectMou,
    G2PRegisterHistoryProjectMou,
    G2PIntakeFormProjectMou,
    G2PRegisterServicePoint,
    G2PRegisterHistoryServicePoint,
    G2PIntakeFormServicePoint,
    G2PRegisterSelfRelianceSurvey,
    G2PRegisterHistorySelfRelianceSurvey,
    G2PIntakeFormSelfRelianceSurvey,
    G2PRegisterHouseholdProgram,
    G2PRegisterHistoryHouseholdProgram,
    G2PIntakeFormHouseholdProgram,
    G2PRegisterHouseholdAsset,
    G2PRegisterHistoryHouseholdAsset,
    G2PIntakeFormHouseholdAsset,
    G2PRegisterIndividualShock,
    G2PRegisterHistoryIndividualShock,
    G2PIntakeFormIndividualShock,
    G2PRegisterHouseholdHousingAndServices,
    G2PRegisterHistoryHouseholdHousingAndServices,
    G2PIntakeFormHouseholdHousingAndServices,
    G2PRegisterIndividualLand,
    G2PRegisterHistoryIndividualLand,
    G2PIntakeFormIndividualLand,
    G2PRegisterIndividualLivelihood,
    G2PRegisterHistoryIndividualLivelihood,
    G2PIntakeFormIndividualLivelihood,
    G2PRegisterIndividualLivestock,
    G2PRegisterHistoryIndividualLivestock,
    G2PIntakeFormIndividualLivestock,
    G2PRegisterIndividualVulnerability,
    G2PRegisterHistoryIndividualVulnerability,
    G2PIntakeFormIndividualVulnerability,
    RpcmsDuplicateAttempt,
    RpcmsReportSubmission,
)
from .register_domain.services import (
    G2PRegisterDomainServiceIndividual,
    G2PRegisterDomainServiceHousehold,
)

_logger = logging.getLogger(_config.logging_default_logger_name)


MODELS = [
    G2PRegisterHousehold,
    G2PRegisterHistoryHousehold,
    G2PIntakeFormHousehold,
    G2PRegisterIndividual,
    G2PRegisterHistoryIndividual,
    G2PIntakeFormIndividual,
    G2PRegisterIndividualDisability,
    G2PRegisterHistoryIndividualDisability,
    G2PIntakeFormIndividualDisability,
    G2PRegisterIndividualProgram,
    G2PRegisterHistoryIndividualProgram,
    G2PIntakeFormIndividualProgram,
    G2PRegisterAssistanceEvent,
    G2PRegisterHistoryAssistanceEvent,
    G2PIntakeFormAssistanceEvent,
    G2PRegisterIdRenewalRequest,
    G2PRegisterHistoryIdRenewalRequest,
    G2PIntakeFormIdRenewalRequest,
    G2PRegisterPartner,
    G2PRegisterHistoryPartner,
    G2PIntakeFormPartner,
    G2PRegisterHouseholdProgram,
    G2PRegisterHistoryHouseholdProgram,
    G2PIntakeFormHouseholdProgram,
    G2PRegisterHouseholdAsset,
    G2PRegisterHistoryHouseholdAsset,
    G2PIntakeFormHouseholdAsset,
    G2PRegisterIndividualShock,
    G2PRegisterHistoryIndividualShock,
    G2PIntakeFormIndividualShock,
    G2PRegisterHouseholdHousingAndServices,
    G2PRegisterHistoryHouseholdHousingAndServices,
    G2PIntakeFormHouseholdHousingAndServices,
    G2PRegisterIndividualLand,
    G2PRegisterHistoryIndividualLand,
    G2PIntakeFormIndividualLand,
    G2PRegisterIndividualLivelihood,
    G2PRegisterHistoryIndividualLivelihood,
    G2PIntakeFormIndividualLivelihood,
    G2PRegisterIndividualLivestock,
    G2PRegisterHistoryIndividualLivestock,
    G2PIntakeFormIndividualLivestock,
    G2PRegisterIndividualVulnerability,
    G2PRegisterHistoryIndividualVulnerability,
    G2PIntakeFormIndividualVulnerability,
    G2PRegisterProject,
    G2PRegisterHistoryProject,
    G2PIntakeFormProject,
    G2PRegisterProjectMou,
    G2PRegisterHistoryProjectMou,
    G2PIntakeFormProjectMou,
    G2PRegisterServicePoint,
    G2PRegisterHistoryServicePoint,
    G2PIntakeFormServicePoint,
    G2PRegisterSelfRelianceSurvey,
    G2PRegisterHistorySelfRelianceSurvey,
    G2PIntakeFormSelfRelianceSurvey,
    RpcmsDuplicateAttempt,
    RpcmsReportSubmission,
]


async def add_missing_columns(model) -> list[str]:
    """Bring an existing table up to its model by adding the columns it lacks; return their names.

    create_migrate() only creates a table that does not exist yet, so a column added to a model later never
    reaches an install whose table already exists. Columns are added nullable unless they carry a server
    default, so existing rows stay valid. Nothing is ever dropped or retyped.
    """
    table = model.__table__
    dialect = postgresql.dialect()
    async with dbengine.get().begin() as conn:
        existing = set(
            (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND table_name = :name"
                    ),
                    {"name": table.name},
                )
            ).scalars()
        )
        if not existing:
            return []
        added = []
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS "{column.name}" ' + column.type.compile(dialect=dialect)
            default = column.server_default
            if default is not None:
                ddl += f" DEFAULT {getattr(default.arg, 'text', default.arg)}"
                if not column.nullable:
                    ddl += " NOT NULL"
            await conn.execute(text(ddl))
            added.append(column.name)
    if added:
        _logger.info("Added columns to %s: %s", table.name, added)
    return added


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize()
        CoreInitializer().initialize()

        G2PRegisterDomainServiceIndividual()
        G2PRegisterDomainServiceHousehold()

        if _config.reporting_api_enabled:
            # Only the staff API sets this. It needs iam_core and a running app, so a failure is logged loudly
            # rather than stopping the service: the registers still work without the report endpoints.
            try:
                from .reporting.controller import RpcmsReportController

                RpcmsReportController().post_init()
            except Exception:
                _logger.exception("Could not register the /rpcms-reports endpoints")
            try:
                from .handover.controller import RpcmsHandoverController

                RpcmsHandoverController().post_init()
            except Exception:
                _logger.exception("Could not register the /rpcms-handovers endpoints")
            try:
                from .jobs.controller import RpcmsJobsController

                RpcmsJobsController().post_init()
            except Exception:
                _logger.exception("Could not register the /rpcms-jobs endpoints")

    def migrate_database(self, args):

        async def migrate():
            _logger.info("Migrating extensions database")
            for model in MODELS:
                await model.create_migrate()
                await add_missing_columns(model)
            from .reporting import create_reporting_views

            async with dbengine.get().begin() as conn:
                await create_reporting_views(conn)

        asyncio.run(migrate())
