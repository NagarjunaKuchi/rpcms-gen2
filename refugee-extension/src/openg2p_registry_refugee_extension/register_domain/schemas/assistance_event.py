from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PIntakeFormSchemaBase,
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
)


class G2PSchemaAssistanceEvent:
    registrant_progres_id: Optional[str] = None
    partner_code: Optional[str] = None
    partner_name: Optional[str] = None
    project_ref: Optional[str] = None
    assistance_type: Optional[str] = None
    distribution_cycle: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    delivery_date: Optional[date] = None
    delivery_location: Optional[str] = None
    capture_channel: Optional[str] = None
    offline_batch_id: Optional[str] = None
    progres_authenticated: Optional[bool] = None
    progres_auth_reference: Optional[str] = None
    progres_authenticated_at: Optional[str] = None
    client_record_id: Optional[str] = None
    captured_at: Optional[str] = None
    officer: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_accuracy_m: Optional[float] = None


class G2PRegisterSchemaAssistanceEvent(G2PRegisterBaseSchema, G2PSchemaAssistanceEvent):
    pass


class G2PIntakeFormSchemaAssistanceEvent(
    G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaAssistanceEvent
):
    pass


class G2PRegisterHistorySchemaAssistanceEvent(G2PRegisterHistorySchema, G2PSchemaAssistanceEvent):
    pass
