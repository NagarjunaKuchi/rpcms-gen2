from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PIntakeFormSchemaBase,
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
)


class G2PSchemaProjectMou:
    mou_number: Optional[str] = None
    ugpass_document_id: Optional[str] = None
    expected_signatures: Optional[int] = None
    expected_eseals: Optional[int] = None
    remarks: Optional[str] = None
    mou_status: Optional[str] = None
    verification_status: Optional[str] = None
    signatures_count: Optional[int] = None
    eseals_count: Optional[int] = None
    document_sha256: Optional[str] = None
    verified_on: Optional[date] = None
    verification_notes: Optional[str] = None


class G2PRegisterSchemaProjectMou(G2PRegisterBaseSchema, G2PSchemaProjectMou):
    pass


class G2PIntakeFormSchemaProjectMou(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaProjectMou):
    pass


class G2PRegisterHistorySchemaProjectMou(G2PRegisterHistorySchema, G2PSchemaProjectMou):
    pass
