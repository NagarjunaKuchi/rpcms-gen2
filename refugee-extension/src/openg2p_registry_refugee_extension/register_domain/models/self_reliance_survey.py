from datetime import date

from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceSelfRelianceSurvey


class G2PSelfRelianceSurvey:
    """One round of the self-reliance survey for a household (demo screen 8). The index and its version are set by the
    registry from the four answers; they are not entered."""
    round_label: Mapped[str] = mapped_column(String, nullable=True, index=True)
    survey_date: Mapped[date] = mapped_column(Date, nullable=True)
    zone: Mapped[str] = mapped_column(String, nullable=True)
    food_source: Mapped[str] = mapped_column(String, nullable=True)
    has_income: Mapped[str] = mapped_column(String, nullable=True)
    income_source: Mapped[str] = mapped_column(String, nullable=True)
    children_in_school: Mapped[str] = mapped_column(String, nullable=True)
    savings_group_member: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
    self_reliance_index: Mapped[int] = mapped_column(Integer, nullable=True)
    index_version: Mapped[str] = mapped_column(String, nullable=True)
    index_computed_on: Mapped[date] = mapped_column(Date, nullable=True)


# Short table names: registry-core adds idx_<table>_search_text_trigram (Postgres limit 63 chars).
class G2PRegisterSelfRelianceSurvey(G2PRegister, G2PSelfRelianceSurvey):
    __tablename__ = "g2p_register_selfrel_surveys"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceSelfRelianceSurvey().construct_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceSelfRelianceSurvey().construct_search_text(self.to_dict())


class G2PRegisterHistorySelfRelianceSurvey(G2PRegisterHistory, G2PSelfRelianceSurvey):
    __tablename__ = "g2p_register_history_selfrel_surveys"


class G2PIntakeFormSelfRelianceSurvey(G2PIntakeForm, G2PRegister, G2PSelfRelianceSurvey):
    __tablename__ = "g2p_intake_form_selfrel_surveys"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceSelfRelianceSurvey().construct_intake_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceSelfRelianceSurvey().construct_search_text(self.to_dict())
