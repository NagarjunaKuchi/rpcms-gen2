import logging
from datetime import datetime, timezone

from sqlalchemy import select

from openg2p_registry_core.services import G2PRegisterDomainService

from ...rules.service_point_overlap import coordinate_error, evaluate_overlap
from .utils.validations import validation_error

_logger = logging.getLogger("g2p-register-servicepoint-service")

REQUIRED = ("point_name", "service_type")
STATUSES = {"PLANNED", "ACTIVE", "CLOSED"}
SEARCH_KEYS = ["point_name", "zone", "service_type", "overlap_status"]
NAME_KEYS = ["point_name", "zone"]


class G2PRegisterDomainServiceServicePoint(G2PRegisterDomainService):
    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            for key in REQUIRED:
                if key in record and not str(record.get(key) or "").strip():
                    validation_error(f"{key} must not be empty")
            problem = coordinate_error(record)
            if problem:
                validation_error(problem)
            status = record.get("status")
            if status not in (None, "") and str(status) not in STATUSES:
                validation_error(f"status must be one of {sorted(STATUSES)}")

    async def post_approve(self, change_request, session):
        """After an approved add or edit: compare the point with other partners' active points of the same service
        type and store OVERLAP / NONE / NOT_CHECKED (and with whom) on the point."""
        from openg2p_registry_core.models import G2PRegisterChangeRequestPayload

        from ...config import Settings
        from ..models import G2PRegisterProject as Project
        from ..models import G2PRegisterServicePoint as Point

        radius = Settings.get_config().service_point_overlap_radius_m
        payload = (
            await session.execute(
                select(G2PRegisterChangeRequestPayload).where(
                    G2PRegisterChangeRequestPayload.change_request_id == change_request.change_request_id
                )
            )
        ).scalar()
        for row in (payload.change_payload if payload else None) or []:
            if row.get("edit_action") not in (None, "ADD", "UPDATE"):
                continue
            if row.get("internal_record_id"):
                query = select(Point).where(Point.internal_record_id == row["internal_record_id"])
            else:
                parent = row.get("link_internal_record_id")
                if not (parent and row.get("point_name")):
                    continue
                query = select(Point).where(Point.link_internal_record_id == parent, Point.point_name == row["point_name"])
            stored = (await session.execute(query.limit(1))).scalar()
            if stored is None:
                _logger.warning("service point %s not found after approval; overlap not checked", row.get("point_name"))
                continue
            others = [
                {"latitude": p.latitude, "longitude": p.longitude, "service_type": p.service_type,
                 "label": f"{proj.partner_code or proj.project_code} · {p.point_name}"}
                for p, proj in (
                    await session.execute(
                        select(Point, Project)
                        .join(Project, Project.internal_record_id == Point.link_internal_record_id)
                        .where(
                            Point.internal_record_id != stored.internal_record_id,
                            Point.link_internal_record_id != stored.link_internal_record_id,
                            Point.status.is_distinct_from("CLOSED"),
                        )
                    )
                ).all()
            ]
            point = {"latitude": stored.latitude, "longitude": stored.longitude, "service_type": stored.service_type}
            for field, value in evaluate_overlap(point, others, radius, datetime.now(timezone.utc).date()).items():
                setattr(stored, field, value)
            await session.flush()

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in SEARCH_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        parts = [str(v).strip() for v in (extra or []) if str(v).strip()]
        parts += [str(payload.get(k) or "").strip() for k in NAME_KEYS if str(payload.get(k) or "").strip()]
        return " ".join(parts).strip() or str(payload.get("functional_record_id") or "").strip()
