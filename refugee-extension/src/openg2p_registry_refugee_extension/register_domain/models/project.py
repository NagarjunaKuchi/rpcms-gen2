from datetime import date

from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceProject


class G2PProject:
    """A partner project funded through AMP (demo screen 3). The funding fields are filled by the registry from AMP, not typed."""
    project_code: Mapped[str] = mapped_column(String, nullable=True, index=True)
    project_name: Mapped[str] = mapped_column(String, nullable=True, index=True)
    partner_code: Mapped[str] = mapped_column(String, nullable=True, index=True)
    partner_name: Mapped[str] = mapped_column(String, nullable=True)
    intervention: Mapped[str] = mapped_column(String, nullable=True)
    area: Mapped[str] = mapped_column(String, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=True)
    target_households: Mapped[int] = mapped_column(Integer, nullable=True)
    household_rate: Mapped[float] = mapped_column(Numeric, nullable=True)
    project_value: Mapped[float] = mapped_column(Numeric, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=True)
    amp_record_no: Mapped[str] = mapped_column(String, nullable=True, index=True)
    amp_status: Mapped[str] = mapped_column(String, nullable=True, index=True)
    amp_donor: Mapped[str] = mapped_column(String, nullable=True)
    amp_commitment: Mapped[float] = mapped_column(Numeric, nullable=True)
    amp_disbursed: Mapped[float] = mapped_column(Numeric, nullable=True)
    amp_checked_on: Mapped[date] = mapped_column(Date, nullable=True)
    amp_notes: Mapped[str] = mapped_column(String, nullable=True)


# Short table names: registry-core adds idx_<table>_search_text_trigram (Postgres limit 63 chars).
class G2PRegisterProject(G2PRegister, G2PProject):
    __tablename__ = "g2p_register_projects"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceProject().construct_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceProject().construct_search_text(self.to_dict())


class G2PRegisterHistoryProject(G2PRegisterHistory, G2PProject):
    __tablename__ = "g2p_register_history_projects"


class G2PIntakeFormProject(G2PIntakeForm, G2PRegister, G2PProject):
    __tablename__ = "g2p_intake_form_projects"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceProject().construct_intake_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceProject().construct_search_text(self.to_dict())
