from datetime import date

from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceIdRenewalRequest


class G2PIdRenewalRequest:
    """A refugee-ID renewal request tracked by RPCMS .

    RPCMS only flags expiry, books the appointment and informs the refugee by SMS. The renewal itself happens in
    UNHCR ProGres v4 (outside RPCMS); the OPM officer closes the request here.
    """

    request_ref: Mapped[str] = mapped_column(String, nullable=True, index=True)
    registrant_progres_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True, index=True)
    card_expiry: Mapped[date] = mapped_column(Date, nullable=True)
    flagged_on: Mapped[date] = mapped_column(Date, nullable=True)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=True)
    appointment_time: Mapped[str] = mapped_column(String, nullable=True)
    appointment_location: Mapped[str] = mapped_column(String, nullable=True)
    closed_on: Mapped[date] = mapped_column(Date, nullable=True)
    closed_by: Mapped[str] = mapped_column(String, nullable=True)
    notification_status: Mapped[str] = mapped_column(String, nullable=True)  # SENT / FAILED / NO_PHONE / NOT_CONFIGURED
    notified_on: Mapped[date] = mapped_column(Date, nullable=True)


# Short table names: registry-core adds idx_<table>_search_text_trigram (Postgres limit 63 chars).
class G2PRegisterIdRenewalRequest(G2PRegister, G2PIdRenewalRequest):
    __tablename__ = "g2p_register_id_renewal"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceIdRenewalRequest().construct_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceIdRenewalRequest().construct_search_text(self.to_dict())


class G2PRegisterHistoryIdRenewalRequest(G2PRegisterHistory, G2PIdRenewalRequest):
    __tablename__ = "g2p_register_history_id_renewal"


class G2PIntakeFormIdRenewalRequest(G2PIntakeForm, G2PRegister, G2PIdRenewalRequest):
    __tablename__ = "g2p_intake_form_id_renewal"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceIdRenewalRequest().construct_intake_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceIdRenewalRequest().construct_search_text(self.to_dict())
