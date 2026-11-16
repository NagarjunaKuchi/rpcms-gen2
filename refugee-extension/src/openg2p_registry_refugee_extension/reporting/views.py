"""Reporting views: the only thing the dashboard (Superset) is given access to. They are re-created on every start
(CREATE OR REPLACE), so a change here reaches an existing install without a reset.

Names are prefixed rpcms_rpt_ so a future refresh/grant can match them by prefix."""
import logging

from sqlalchemy import text

_logger = logging.getLogger("rpcms-reporting")

# Quarter label of a date, e.g. 2026-Q3.
_Q = "to_char({col}, 'YYYY\"-Q\"Q')"

REPORTING_VIEWS_SQL = [
    """
    CREATE OR REPLACE VIEW rpcms_rpt_summary AS
    SELECT
      (SELECT count(*) FROM g2p_register_partners WHERE record_status = 'ACTIVE')                          AS partners_active,
      (SELECT count(*) FROM g2p_register_partners
         WHERE record_status = 'ACTIVE' AND compliance_status = 'COMPLIANT')                               AS partners_compliant,
      (SELECT count(*) FROM g2p_register_assistance_event WHERE record_status = 'ACTIVE')                  AS events_total,
      (SELECT count(*) FROM g2p_register_assistance_event
         WHERE record_status = 'ACTIVE' AND progres_authenticated IS TRUE)                                 AS events_authenticated,
      (SELECT count(DISTINCT registrant_progres_id) FROM g2p_register_assistance_event
         WHERE record_status = 'ACTIVE')                                                                   AS persons_reached,
      (SELECT count(*) FROM rpcms_duplicate_attempt)                                                       AS duplicates_flagged
    """,
    """
    CREATE OR REPLACE VIEW rpcms_rpt_partner_performance AS
    SELECT p.partner_code,
           p.organisation_name                                  AS partner_name,
           p.compliance_status,
           COALESCE(pl.planned_households, 0)                    AS planned_households,
           COALESCE(ev.persons_reached, 0)                       AS persons_reached,
           COALESCE(ev.events, 0)                                AS events,
           COALESCE(ev.events_authenticated, 0)                  AS events_authenticated
    FROM g2p_register_partners p
    LEFT JOIN (SELECT partner_code, sum(target_households) AS planned_households
               FROM g2p_register_projects WHERE record_status = 'ACTIVE' GROUP BY partner_code) pl
           ON pl.partner_code = p.partner_code
    LEFT JOIN (SELECT partner_code,
                      count(DISTINCT registrant_progres_id)                          AS persons_reached,
                      count(*)                                                        AS events,
                      count(*) FILTER (WHERE progres_authenticated IS TRUE)           AS events_authenticated
               FROM g2p_register_assistance_event WHERE record_status = 'ACTIVE' GROUP BY partner_code) ev
           ON ev.partner_code = p.partner_code
    WHERE p.record_status = 'ACTIVE'
    """,
    """
    CREATE OR REPLACE VIEW rpcms_rpt_reach_by_location AS
    SELECT COALESCE(NULLIF(trim(delivery_location), ''), '(not recorded)') AS delivery_location,
           assistance_type,
           count(*)                                    AS events,
           count(DISTINCT registrant_progres_id)       AS persons_reached
    FROM g2p_register_assistance_event
    WHERE record_status = 'ACTIVE'
    GROUP BY 1, 2
    """,
    """
    CREATE OR REPLACE VIEW rpcms_rpt_expenditure AS
    SELECT e.project_ref                                  AS project_code,
           pr.project_name,
           pr.partner_code,
           pr.amp_record_no,
           pr.amp_status,
           e.currency,
           %(q)s                                          AS quarter,
           sum(e.amount)                                  AS amount,
           count(*)                                       AS events
    FROM g2p_register_assistance_event e
    LEFT JOIN g2p_register_projects pr
           ON pr.project_code = e.project_ref AND pr.record_status = 'ACTIVE'
    WHERE e.record_status = 'ACTIVE' AND e.amount IS NOT NULL AND e.delivery_date IS NOT NULL
    GROUP BY e.project_ref, pr.project_name, pr.partner_code, pr.amp_record_no, pr.amp_status, e.currency,
             %(q)s
    """ % {"q": _Q.format(col="e.delivery_date")},
    """
    CREATE OR REPLACE VIEW rpcms_rpt_events_by_month AS
    SELECT date_trunc('month', delivery_date)::date                              AS month,
           count(*)                                                              AS events,
           count(*) FILTER (WHERE progres_authenticated IS TRUE)                 AS events_authenticated
    FROM g2p_register_assistance_event
    WHERE record_status = 'ACTIVE' AND delivery_date IS NOT NULL
    GROUP BY 1
    """,
    """
    CREATE OR REPLACE VIEW rpcms_rpt_duplicates_by_month AS
    SELECT date_trunc('month', detected_at)::date AS month, count(*) AS duplicates_flagged
    FROM rpcms_duplicate_attempt
    GROUP BY 1
    """,
    """
    CREATE OR REPLACE VIEW rpcms_rpt_self_reliance AS
    SELECT round_label,
           count(*)                                                       AS households_surveyed,
           count(*) FILTER (WHERE has_income = 'YES')                     AS households_with_income,
           count(*) FILTER (WHERE self_reliance_index IS NOT NULL)        AS households_scored,
           round(avg(self_reliance_index)::numeric, 1)                    AS average_index
    FROM g2p_register_selfrel_surveys
    WHERE record_status = 'ACTIVE' AND round_label IS NOT NULL
    GROUP BY round_label
    """,
    """
    CREATE OR REPLACE VIEW rpcms_rpt_submissions AS
    SELECT submitted_at, system, quarter, status, records_sent, external_reference, submitted_by, detail
    FROM rpcms_report_submission
    """,
]


# The dashboard connects as a read-only role that can see these views and nothing else (no register tables, no
# personal data). The role is created with the database; where it does not exist, nothing is granted.
GRANT_SQL = """
DO $$
DECLARE v text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rpcms_reporting') THEN
    FOR v IN SELECT viewname FROM pg_views WHERE schemaname = current_schema() AND viewname LIKE 'rpcms\\_rpt\\_%' LOOP
      EXECUTE format('GRANT SELECT ON %I TO rpcms_reporting', v);
    END LOOP;
  END IF;
END $$;
"""


async def create_reporting_views(conn) -> None:
    """Create the views on an open (begin()) connection. The tables they read must already exist."""
    for sql in REPORTING_VIEWS_SQL:
        await conn.execute(text(sql))
    await conn.execute(text(GRANT_SQL))
    _logger.info("Reporting views (rpcms_rpt_*) created")
