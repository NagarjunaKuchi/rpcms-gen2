from datetime import date

from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServicePartner


class G2PPartner:
    """A partner organisation (NGO / agency) registered to work in a settlement (RPCMS demo screen 1).

    The organisation's URSB registration and NGO Bureau permit are checked automatically when the
    registration is approved (compliance_* fields are set by the registry, not typed by staff).
    """

    organisation_name: Mapped[str] = mapped_column(String, nullable=True, index=True)
    partner_code: Mapped[str] = mapped_column(String, nullable=True, index=True)
    ursb_registration_no: Mapped[str] = mapped_column(String, nullable=True, index=True)
    ngo_permit_no: Mapped[str] = mapped_column(String, nullable=True, index=True)
    proposed_area: Mapped[str] = mapped_column(String, nullable=True)
    sector: Mapped[str] = mapped_column(String, nullable=True)
    country_director: Mapped[str] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str] = mapped_column(String, nullable=True)

    ursb_status: Mapped[str] = mapped_column(String, nullable=True)
    ursb_registered_name: Mapped[str] = mapped_column(String, nullable=True)
    ngo_permit_status: Mapped[str] = mapped_column(String, nullable=True)
    permit_valid_to: Mapped[date] = mapped_column(Date, nullable=True)
    permit_renewal_alert_date: Mapped[date] = mapped_column(Date, nullable=True)
    compliance_status: Mapped[str] = mapped_column(String, nullable=True, index=True)
    compliance_checked_on: Mapped[date] = mapped_column(Date, nullable=True)
    compliance_notes: Mapped[str] = mapped_column(String, nullable=True)


# Short table names: registry-core adds idx_<table>_search_text_trigram (Postgres limit 63 chars).
class G2PRegisterPartner(G2PRegister, G2PPartner):
    __tablename__ = "g2p_register_partners"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServicePartner().construct_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServicePartner().construct_search_text(self.to_dict())


class G2PRegisterHistoryPartner(G2PRegisterHistory, G2PPartner):
    __tablename__ = "g2p_register_history_partners"


class G2PIntakeFormPartner(G2PIntakeForm, G2PRegister, G2PPartner):
    __tablename__ = "g2p_intake_form_partners"

    def get_record_name_fields(self) -> str:
        return G2PRegisterDomainServicePartner().construct_intake_record_name(self.to_dict())

    def get_search_text_fields(self) -> str:
        return G2PRegisterDomainServicePartner().construct_search_text(self.to_dict())
