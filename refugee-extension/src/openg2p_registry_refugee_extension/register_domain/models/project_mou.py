from datetime import date

from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceProjectMou


class G2PProjectMou:
    """The project's e-MoU, signed in UGPass (demo screen 2). Signatories sign in their own UGPass app; the registry
    records the MoU and checks the UGPass document (signatures, e-Seals, unaltered content). Result fields are set by the registry."""
    mou_number: Mapped[str] = mapped_column(String, nullable=True, index=True)
    ugpass_document_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    expected_signatures: Mapped[int] = mapped_column(Integer, nullable=True)
    expected_eseals: Mapped[int] = mapped_column(Integer, nullable=True)
    remarks: Mapped[str] = mapped_column(String, nullable=True)
    verification_status: Mapped[str] = mapped_column(String, nullable=True, index=True)
    signatures_count: Mapped[int] = mapped_column(Integer, nullable=True)
    eseals_count: Mapped[int] = mapped_column(Integer, nullable=True)
    document_sha256: Mapped[str] = mapped_column(String, nullable=True)
    verified_on: Mapped[date] = mapped_column(Date, nullable=True)
    verification_notes: Mapped[str] = mapped_column(String, nullable=True)


# Short table names: registry-core adds idx_<table>_search_text_trigram (Postgres limit 63 chars).
class G2PRegisterProjectMou(G2PRegister, G2PProjectMou):
    __tablename__ = "g2p_register_project_mou"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceProjectMou().construct_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceProjectMou().construct_search_text(self.to_dict())


class G2PRegisterHistoryProjectMou(G2PRegisterHistory, G2PProjectMou):
    __tablename__ = "g2p_register_history_project_mou"


class G2PIntakeFormProjectMou(G2PIntakeForm, G2PRegister, G2PProjectMou):
    __tablename__ = "g2p_intake_form_project_mou"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceProjectMou().construct_intake_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceProjectMou().construct_search_text(self.to_dict())
