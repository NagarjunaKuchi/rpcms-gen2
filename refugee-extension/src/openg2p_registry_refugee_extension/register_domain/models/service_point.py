from datetime import date

from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceServicePoint


class G2PServicePoint:
    """A project's distribution / service point (demo screen 3). The overlap fields are set by the registry by comparing
    with other partners' points of the same service type."""
    point_name: Mapped[str] = mapped_column(String, nullable=True, index=True)
    zone: Mapped[str] = mapped_column(String, nullable=True)
    service_type: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True)
    latitude: Mapped[float] = mapped_column(Numeric, nullable=True)
    longitude: Mapped[float] = mapped_column(Numeric, nullable=True)
    overlap_status: Mapped[str] = mapped_column(String, nullable=True, index=True)
    overlap_with: Mapped[str] = mapped_column(String, nullable=True)
    overlap_checked_on: Mapped[date] = mapped_column(Date, nullable=True)


# Short table names: registry-core adds idx_<table>_search_text_trigram (Postgres limit 63 chars).
class G2PRegisterServicePoint(G2PRegister, G2PServicePoint):
    __tablename__ = "g2p_register_service_points"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceServicePoint().construct_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceServicePoint().construct_search_text(self.to_dict())


class G2PRegisterHistoryServicePoint(G2PRegisterHistory, G2PServicePoint):
    __tablename__ = "g2p_register_history_service_points"


class G2PIntakeFormServicePoint(G2PIntakeForm, G2PRegister, G2PServicePoint):
    __tablename__ = "g2p_intake_form_service_points"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceServicePoint().construct_intake_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceServicePoint().construct_search_text(self.to_dict())
