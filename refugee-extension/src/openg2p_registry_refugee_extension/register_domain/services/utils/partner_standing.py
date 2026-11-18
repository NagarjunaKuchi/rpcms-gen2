from sqlalchemy import select


async def partner_standing(session, partner_code: str):
    """(compliance_status, compliance_notes) of the active partner with this code, or None when there is none."""
    from ...models import G2PRegisterPartner as Partner

    row = (await session.execute(select(Partner.compliance_status, Partner.compliance_notes).where(
        Partner.partner_code == partner_code, Partner.record_status == "ACTIVE").limit(1))).first()
    return (row[0], row[1]) if row else None
