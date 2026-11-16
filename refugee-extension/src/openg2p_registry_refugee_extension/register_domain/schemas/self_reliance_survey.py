from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PIntakeFormSchemaBase,
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
)


class G2PSchemaSelfRelianceSurvey:
    round_label: Optional[str] = None
    survey_date: Optional[date] = None
    zone: Optional[str] = None
    food_source: Optional[str] = None
    has_income: Optional[str] = None
    income_source: Optional[str] = None
    children_in_school: Optional[str] = None
    savings_group_member: Optional[str] = None
    notes: Optional[str] = None
    self_reliance_index: Optional[int] = None
    index_version: Optional[str] = None
    index_computed_on: Optional[date] = None


class G2PRegisterSchemaSelfRelianceSurvey(G2PRegisterBaseSchema, G2PSchemaSelfRelianceSurvey):
    pass


class G2PIntakeFormSchemaSelfRelianceSurvey(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaSelfRelianceSurvey):
    pass


class G2PRegisterHistorySchemaSelfRelianceSurvey(G2PRegisterHistorySchema, G2PSchemaSelfRelianceSurvey):
    pass
