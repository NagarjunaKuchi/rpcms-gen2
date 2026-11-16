from openg2p_registry_core.config import Settings as CoreSettings
from pydantic_settings import SettingsConfigDict

from . import __version__


class Settings(CoreSettings):
    """Refugee Partnership Coordination & Monitoring System (RPCMS) settings.

    Every value is read from the environment with the prefix ``REGISTRY_EXTENSIONS_`` (e.g.
    ``REGISTRY_EXTENSIONS_URSB_BASE_URL``). Secrets (API keys) must come from the deployment's secret store.
    A system whose base URL is empty is *not configured*: records are then marked NOT_CHECKED and nothing is
    invented. See docs/integrations.md for the request/response contract each adapter expects.
    """

    model_config = SettingsConfigDict(
        env_prefix="registry_extensions_", env_file=".env", extra="allow"
    )

    openapi_title: str = "RPCMS Registry Extensions"
    openapi_description: str = """
        FastAPI service for the Refugee Partnership Coordination & Monitoring System registers
        (individuals, households, partners, assistance events, ID renewals).
        """
    openapi_version: str = __version__

    # --- external systems (empty base URL = not configured) -------------------------------------------
    integration_timeout_seconds: float = 10.0
    integration_retries: int = 2  # extra attempts on network errors, HTTP 429 and 5xx

    ursb_base_url: str = ""  # Uganda Registration Services Bureau: organisation registration lookup
    ursb_api_key: str = ""
    ngo_bureau_base_url: str = ""  # NGO Bureau: operating permit lookup
    ngo_bureau_api_key: str = ""
    progres_base_url: str = ""  # UNHCR ProGres v4: ID confirmation
    progres_api_key: str = ""
    sms_base_url: str = ""  # SMS gateway
    sms_api_key: str = ""
    sms_sender_id: str = ""

    # --- business rules ----------------------------------------------------------------------------------
    permit_renewal_alert_days: int = 60  # alert this many days before an NGO permit expires
