from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PIntakeFormSchemaBase,
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
)


class G2PSchemaServicePoint:
    point_name: Optional[str] = None
    zone: Optional[str] = None
    service_type: Optional[str] = None
    status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    overlap_status: Optional[str] = None
    overlap_with: Optional[str] = None
    overlap_checked_on: Optional[date] = None


class G2PRegisterSchemaServicePoint(G2PRegisterBaseSchema, G2PSchemaServicePoint):
    pass


class G2PIntakeFormSchemaServicePoint(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaServicePoint):
    pass


class G2PRegisterHistorySchemaServicePoint(G2PRegisterHistorySchema, G2PSchemaServicePoint):
    pass
