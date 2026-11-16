"""Creates the RPCMS national dashboard in Superset through its REST API. Idempotent: run again and it updates
what exists. Exits non-zero if a chart cannot be queried, so a broken dashboard fails the deploy instead of
sitting there empty.

DEV: signs in as the local admin. Everything is a read of the rpcms_rpt_* views."""
import json
import os
import sys
import time

import requests

URL = os.environ["SUPERSET_URL"].rstrip("/")
ADMIN_PASSWORD = os.environ["SUPERSET_ADMIN_PASSWORD"]
DB_NAME = "RPCMS"
DB_URI = "postgresql+psycopg2://rpcms_reporting:{}@postgres:5432/registry".format(os.environ["REPORTING_DB_PASSWORD"])
SLUG = "rpcms-national"
TITLE = "RPCMS - National Dashboard"

s = requests.Session()


def die(msg):
    print("ERROR:", msg, file=sys.stderr)
    sys.exit(1)


def call(method, path, **kw):
    r = s.request(method, URL + path, timeout=120, **kw)
    if r.status_code >= 400:
        die(f"{method} {path} -> {r.status_code} {r.text[:600]}")
    return r.json() if r.content else {}


def login():
    for _ in range(30):
        r = s.post(URL + "/api/v1/security/login", json={"username": "admin", "password": ADMIN_PASSWORD, "provider": "db", "refresh": True})
        if r.status_code == 200:
            s.headers["Authorization"] = "Bearer " + r.json()["access_token"]
            csrf = call("GET", "/api/v1/security/csrf_token/")["result"]
            s.headers.update({"X-CSRFToken": csrf, "Referer": URL})
            return
        time.sleep(3)
    die("could not sign in to Superset")


def rison(value: str) -> str:
    return "'" + value.replace("!", "!!").replace("'", "!'") + "'"


def find(endpoint, column, value):
    q = f"(filters:!((col:{column},opr:eq,value:{rison(value)})))"
    res = call("GET", f"/api/v1/{endpoint}/", params={"q": q})
    return res["result"][0]["id"] if res.get("result") else None


def sum_metric(col, label=None):
    return {"expressionType": "SIMPLE", "column": {"column_name": col}, "aggregate": "SUM", "label": label or col}


def max_metric(col, label):
    return {"expressionType": "SIMPLE", "column": {"column_name": col}, "aggregate": "MAX", "label": label}


def database_id():
    found = find("database", "database_name", DB_NAME)
    if found:
        return found
    return call("POST", "/api/v1/database/", json={"database_name": DB_NAME, "sqlalchemy_uri": DB_URI,
                                                   "expose_in_sqllab": False, "allow_dml": False})["id"]


def dataset_id(db_id, table):
    found = find("dataset", "table_name", table)
    if found:
        return found
    return call("POST", "/api/v1/dataset/", json={"database": db_id, "schema": "public", "table_name": table})["id"]


def dashboard_id():
    found = find("dashboard", "slug", SLUG)
    if found:
        return found
    return call("POST", "/api/v1/dashboard/", json={"dashboard_title": TITLE, "slug": SLUG, "published": True})["id"]


def query_context(viz, ds_id, params):
    """What Superset's own UI would save with the chart. Without it the server refuses to run the chart
    ("Chart has no query context saved"), which also makes it impossible to check from here."""
    metrics = params.get("metrics") or ([params["metric"]] if params.get("metric") else [])
    if viz == "table":
        query = {"columns": params["all_columns"], "metrics": [], "row_limit": params.get("row_limit", 1000)}
    elif viz == "big_number_total":
        query = {"columns": [], "metrics": metrics, "row_limit": 1}
    else:  # echarts_timeseries_bar
        x = params["x_axis"]
        axis = ({"timeGrain": params["time_grain_sqla"], "columnType": "BASE_AXIS", "sqlExpression": x, "label": x,
                 "expressionType": "SQL"} if params.get("time_grain_sqla") else x)
        query = {"columns": [axis] + list(params.get("groupby") or []), "metrics": metrics,
                 "row_limit": params.get("row_limit", 10000)}
    query.update({"filters": [], "extras": {"having": "", "where": ""}, "applied_time_extras": {}, "orderby": [],
                  "annotation_layers": [], "series_columns": [], "order_desc": True, "url_params": {},
                  "custom_params": {}, "custom_form_data": {}})
    return {"datasource": {"id": ds_id, "type": "table"}, "force": False, "queries": [query], "form_data": params,
            "result_format": "json", "result_type": "full"}


def upsert_chart(name, viz, ds_id, params, dash_id):
    params = {**params, "viz_type": viz, "datasource": f"{ds_id}__table", "adhoc_filters": [], "extra_form_data": {}}
    body = {"slice_name": name, "viz_type": viz, "datasource_id": ds_id, "datasource_type": "table",
            "params": json.dumps(params), "query_context": json.dumps(query_context(viz, ds_id, params)),
            "dashboards": [dash_id]}
    found = find("chart", "slice_name", name)
    if found:
        call("PUT", f"/api/v1/chart/{found}", json=body)
        return found
    return call("POST", "/api/v1/chart/", json=body)["id"]


def table_params(columns):
    return {"query_mode": "raw", "all_columns": columns, "row_limit": 1000, "server_page_length": 10,
            "include_search": True, "show_cell_bars": False, "order_desc": True, "table_timestamp_format": "smart_date"}


def big_number(col, label):
    return {"metric": max_metric(col, label), "y_axis_format": "SMART_NUMBER", "header_font_size": 0.5,
            "subheader_font_size": 0.15, "time_format": "smart_date"}


def main():
    login()
    db = database_id()
    ds = {t: dataset_id(db, t) for t in (
        "rpcms_rpt_summary", "rpcms_rpt_partner_performance", "rpcms_rpt_reach_by_location", "rpcms_rpt_expenditure",
        "rpcms_rpt_events_by_month", "rpcms_rpt_self_reliance", "rpcms_rpt_submissions")}
    dash = dashboard_id()

    summary = ds["rpcms_rpt_summary"]
    charts = {}
    charts["partners"] = upsert_chart("Partners compliance-verified", "big_number_total", summary, big_number("partners_compliant", "Partners compliance-verified"), dash)
    charts["authenticated"] = upsert_chart("Assistance events authenticated with ProGres", "big_number_total", summary, big_number("events_authenticated", "Authenticated events"), dash)
    charts["duplicates"] = upsert_chart("Duplicate assistance cases flagged", "big_number_total", summary, big_number("duplicates_flagged", "Duplicates flagged"), dash)
    charts["persons"] = upsert_chart("Persons reached with assistance", "big_number_total", summary, big_number("persons_reached", "Persons reached"), dash)
    charts["reach"] = upsert_chart("Reach by delivery location", "echarts_timeseries_bar", ds["rpcms_rpt_reach_by_location"], {
        "x_axis": "delivery_location", "metrics": [sum_metric("persons_reached", "Persons reached")],
        "groupby": ["assistance_type"], "row_limit": 1000, "show_legend": True, "stack": "Stack", "orientation": "vertical"}, dash)
    charts["monthly"] = upsert_chart("Assistance events by month", "echarts_timeseries_bar", ds["rpcms_rpt_events_by_month"], {
        "x_axis": "month", "time_grain_sqla": "P1M", "metrics": [sum_metric("events", "Events"), sum_metric("events_authenticated", "Authenticated")],
        "groupby": [], "row_limit": 10000, "show_legend": True, "orientation": "vertical"}, dash)
    charts["sr_index"] = upsert_chart("Self-reliance index by survey round", "echarts_timeseries_bar", ds["rpcms_rpt_self_reliance"], {
        "x_axis": "round_label", "metrics": [max_metric("average_index", "Average index (0-100)")],
        "groupby": [], "row_limit": 1000, "show_legend": False, "orientation": "vertical"}, dash)
    charts["sr_income"] = upsert_chart("Households with an income source by survey round", "echarts_timeseries_bar", ds["rpcms_rpt_self_reliance"], {
        "x_axis": "round_label", "metrics": [sum_metric("households_surveyed", "Surveyed"), sum_metric("households_with_income", "With income")],
        "groupby": [], "row_limit": 1000, "show_legend": True, "orientation": "vertical"}, dash)
    charts["partner_table"] = upsert_chart("Partner performance", "table", ds["rpcms_rpt_partner_performance"], table_params(
        ["partner_name", "compliance_status", "planned_households", "persons_reached", "events", "events_authenticated"]), dash)
    charts["expenditure"] = upsert_chart("Expenditure by project and quarter", "table", ds["rpcms_rpt_expenditure"], table_params(
        ["quarter", "project_code", "project_name", "partner_code", "amp_record_no", "amp_status", "currency", "amount", "events"]), dash)
    charts["submissions"] = upsert_chart("Reports sent to AMP and NIMES", "table", ds["rpcms_rpt_submissions"], table_params(
        ["submitted_at", "system", "quarter", "status", "records_sent", "external_reference", "submitted_by", "detail"]), dash)

    names = {"partners": "Partners compliance-verified", "authenticated": "Assistance events authenticated with ProGres",
             "duplicates": "Duplicate assistance cases flagged", "persons": "Persons reached with assistance",
             "reach": "Reach by delivery location", "monthly": "Assistance events by month",
             "partner_table": "Partner performance", "expenditure": "Expenditure by project and quarter",
             "submissions": "Reports sent to AMP and NIMES",
             "sr_index": "Self-reliance index by survey round", "sr_income": "Households with an income source by survey round"}

    def chart_node(key, row, width, height):
        node = f"CHART-{key}"
        return node, {"type": "CHART", "id": node, "children": [], "parents": ["ROOT_ID", "GRID_ID", row],
                      "meta": {"width": width, "height": height, "chartId": charts[key], "sliceName": names[key]}}

    layout = {"DASHBOARD_VERSION_KEY": "v2", "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
              "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": TITLE}}}
    rows = [("ROW-kpi", [("partners", 3, 16), ("authenticated", 3, 16), ("duplicates", 3, 16), ("persons", 3, 16)]),
            ("ROW-reach", [("reach", 6, 50), ("monthly", 6, 50)]),
            ("ROW-selfreliance", [("sr_index", 6, 40), ("sr_income", 6, 40)]),
            ("ROW-partners", [("partner_table", 12, 30)]),
            ("ROW-money", [("expenditure", 12, 40)]),
            ("ROW-sent", [("submissions", 12, 30)])]
    grid = []
    for row, items in rows:
        kids = []
        for key, w, h in items:
            node, spec = chart_node(key, row, w, h)
            layout[node] = spec
            kids.append(node)
        layout[row] = {"type": "ROW", "id": row, "children": kids, "parents": ["ROOT_ID", "GRID_ID"],
                       "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        grid.append(row)
    layout["GRID_ID"] = {"type": "GRID", "id": "GRID_ID", "children": grid, "parents": ["ROOT_ID"]}
    call("PUT", f"/api/v1/dashboard/{dash}", json={"dashboard_title": TITLE, "published": True,
                                                   "position_json": json.dumps(layout), "json_metadata": json.dumps({"refresh_frequency": 0})})

    failed = []
    for key, cid in charts.items():
        r = s.get(f"{URL}/api/v1/chart/{cid}/data/", timeout=120)
        ok = r.status_code == 200 and not any(q.get("error") for q in r.json().get("result", []))
        print(f"  chart {names[key]!r}: {'ok' if ok else 'FAILED ' + r.text[:300]}")
        if not ok:
            failed.append(names[key])
    if failed:
        die("charts that cannot be queried: " + ", ".join(failed))
    print(f"Dashboard ready: {URL}/superset/dashboard/{SLUG}/")


if __name__ == "__main__":
    main()
