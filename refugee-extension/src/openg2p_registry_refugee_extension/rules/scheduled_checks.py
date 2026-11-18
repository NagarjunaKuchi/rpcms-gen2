"""Rules for the daily scheduled checks. Pure functions (no I/O, no platform imports)."""
from datetime import date, timedelta


def permit_alert_due(today: date, alert_date: date | None, valid_to: date | None, sent_on: date | None) -> bool:
    """Tell the partner their NGO permit is about to expire: from the alert date until the permit expires, once per
    permit. 'Once' means no alert sent on or after the current alert date; a renewed permit moves the alert date
    later, so it alerts again."""
    if alert_date is None or valid_to is None:
        return False
    if not (alert_date <= today <= valid_to):
        return False
    return sent_on is None or sent_on < alert_date


def permit_sms_text(organisation: str | None, valid_to: date) -> str:
    return (f"OPM Refugees: the NGO operating permit for {organisation or 'your organisation'} expires on {valid_to}. "
            "Please renew it to keep recording assistance.")


def id_expiry_due(today: date, card_expiry: date | None, alert_days: int) -> bool:
    """A card is close to expiry when it expires from today up to `alert_days` days ahead. Cards that expired earlier
    are not picked up, so the first run does not flood staff with long-expired cards."""
    return card_expiry is not None and today <= card_expiry <= today + timedelta(days=alert_days)


def renewal_ref(progres_id: str, card_expiry: date) -> str:
    """Same person and same card expiry always give the same reference, so a rerun never flags them twice."""
    return f"AUTO-{progres_id}-{card_expiry:%Y%m%d}"
