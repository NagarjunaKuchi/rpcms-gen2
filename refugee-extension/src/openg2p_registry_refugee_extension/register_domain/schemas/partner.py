from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PIntakeFormSchemaBase,
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
)


class G2PSchemaPartner:
    organisation_name: Optional[str] = None
    partner_code: Optional[str] = None
    ursb_registration_no: Optional[str] = None
    ngo_permit_no: Optional[str] = None
    proposed_area: Optional[str] = None
    operating_district: Optional[str] = None
    sector: Optional[str] = None
    country_director: Optional[str] = None
    contact_phone: Optional[str] = None
    ursb_status: Optional[str] = None
    ursb_registered_name: Optional[str] = None
    ngo_permit_status: Optional[str] = None
    permit_area_status: Optional[str] = None
    permit_valid_to: Optional[date] = None
    permit_renewal_alert_date: Optional[date] = None
    compliance_status: Optional[str] = None
    compliance_checked_on: Optional[date] = None
    compliance_notes: Optional[str] = None


class G2PRegisterSchemaPartner(G2PRegisterBaseSchema, G2PSchemaPartner):
    pass


class G2PIntakeFormSchemaPartner(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaPartner):
    pass


class G2PRegisterHistorySchemaPartner(G2PRegisterHistorySchema, G2PSchemaPartner):
    pass
