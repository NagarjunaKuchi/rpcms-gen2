from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PIntakeFormSchemaBase,
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
)


class G2PSchemaProject:
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    partner_code: Optional[str] = None
    partner_name: Optional[str] = None
    intervention: Optional[str] = None
    area: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    target_households: Optional[int] = None
    household_rate: Optional[float] = None
    project_value: Optional[float] = None
    currency: Optional[str] = None
    amp_record_no: Optional[str] = None
    amp_status: Optional[str] = None
    amp_donor: Optional[str] = None
    amp_commitment: Optional[float] = None
    amp_disbursed: Optional[float] = None
    amp_checked_on: Optional[date] = None
    amp_notes: Optional[str] = None


class G2PRegisterSchemaProject(G2PRegisterBaseSchema, G2PSchemaProject):
    pass


class G2PIntakeFormSchemaProject(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaProject):
    pass


class G2PRegisterHistorySchemaProject(G2PRegisterHistorySchema, G2PSchemaProject):
    pass
