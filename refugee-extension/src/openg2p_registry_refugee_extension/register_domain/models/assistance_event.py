from datetime import date

from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from sqlalchemy import Boolean, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceAssistanceEvent


class G2PAssistanceEvent:
    """One assistance delivery reported by a partner for a registrant (RPCMS).

    The duplicate-assistance rule is the platform's own register deduplication:
    EXACT match on (registrant_progres_id, assistance_type, distribution_cycle),
    configured in meta_data/register-metadata/g2p_register_schemas.sql.
    """

    registrant_progres_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    partner_code: Mapped[str] = mapped_column(String, nullable=True, index=True)
    partner_name: Mapped[str] = mapped_column(String, nullable=True)
    project_ref: Mapped[str] = mapped_column(String, nullable=True)
    assistance_type: Mapped[str] = mapped_column(String, nullable=True, index=True)
    distribution_cycle: Mapped[str] = mapped_column(String, nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=True)
    unit: Mapped[str] = mapped_column(String, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=True)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=True)
    delivery_location: Mapped[str] = mapped_column(String, nullable=True)
    capture_channel: Mapped[str] = mapped_column(String, nullable=True)
    offline_batch_id: Mapped[str] = mapped_column(String, nullable=True)
    progres_authenticated: Mapped[bool] = mapped_column(Boolean, nullable=True)
    # Set by the registry from the ProGres answer, never typed or sent by a phone. Empty when ProGres gave none.
    progres_auth_reference: Mapped[str] = mapped_column(String, nullable=True, index=True)  # ProGres transaction reference
    progres_authenticated_at: Mapped[str] = mapped_column(String, nullable=True)  # ISO-8601 time ProGres gave for the check
    # Field capture (handover recorded on a phone, possibly offline, then synced).
    client_record_id: Mapped[str] = mapped_column(String, nullable=True, index=True)  # the phone's own id; makes a retried sync safe
    captured_at: Mapped[str] = mapped_column(String, nullable=True)  # ISO-8601 time on the phone when the handover was recorded
    officer: Mapped[str] = mapped_column(String, nullable=True)
    gps_latitude: Mapped[float] = mapped_column(Numeric, nullable=True)
    gps_longitude: Mapped[float] = mapped_column(Numeric, nullable=True)
    gps_accuracy_m: Mapped[float] = mapped_column(Numeric, nullable=True)


# Table names are kept short: registry-core adds an index named
# idx_<table>_search_text_trigram, which Postgres limits to 63 characters.
class G2PRegisterAssistanceEvent(G2PRegister, G2PAssistanceEvent):
    __tablename__ = "g2p_register_assistance_event"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceAssistanceEvent().construct_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceAssistanceEvent().construct_search_text(self.to_dict())


class G2PRegisterHistoryAssistanceEvent(G2PRegisterHistory, G2PAssistanceEvent):
    __tablename__ = "g2p_register_history_assistance_event"


class G2PIntakeFormAssistanceEvent(G2PIntakeForm, G2PRegister, G2PAssistanceEvent):
    __tablename__ = "g2p_intake_form_assistance_event"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServiceAssistanceEvent().construct_intake_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServiceAssistanceEvent().construct_search_text(self.to_dict())
