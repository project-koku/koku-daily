import logging

import dash_html_components as html
from kokudaily.charts.utils import generate_table
from kokudaily.reports import run_reports

LOG = logging.getLogger(__name__)


def display_marketing():
    """Display marketing metrics."""
    LOG.info("Displaying marketing metrics.")

    report_data = run_reports(filter_target="marketing")
    mkt_metrics = report_data.get("marketing", {})
    page_div = [html.H3("Marketing")]
    for report_name, report_data in mkt_metrics.items():
        columns = report_data.get("columns", [])
        data = report_data.get("data", [])
        page_div.append(html.H4(report_name))
        page_div.append(generate_table(columns, data))

    return html.Div(page_div)
