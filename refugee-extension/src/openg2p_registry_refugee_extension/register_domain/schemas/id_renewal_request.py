from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PIntakeFormSchemaBase,
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
)


class G2PSchemaIdRenewalRequest:
    request_ref: Optional[str] = None
    registrant_progres_id: Optional[str] = None
    service_type: Optional[str] = None
    status: Optional[str] = None
    card_expiry: Optional[date] = None
    flagged_on: Optional[date] = None
    appointment_date: Optional[date] = None
    appointment_time: Optional[str] = None
    appointment_location: Optional[str] = None
    closed_on: Optional[date] = None
    closed_by: Optional[str] = None


class G2PRegisterSchemaIdRenewalRequest(G2PRegisterBaseSchema, G2PSchemaIdRenewalRequest):
    pass


class G2PIntakeFormSchemaIdRenewalRequest(
    G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaIdRenewalRequest
):
    pass


class G2PRegisterHistorySchemaIdRenewalRequest(G2PRegisterHistorySchema, G2PSchemaIdRenewalRequest):
    pass
