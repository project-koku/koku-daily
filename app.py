import logging
import re
import sys

import dash
import dash_core_components as dcc
import dash_html_components as html
from kokudaily.charts import display_engineering
from kokudaily.charts import display_index
from kokudaily.charts import display_marketing
from kokudaily.config import Config

root = logging.getLogger()
root.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
root.addHandler(handler)

LOG = logging.getLogger(__name__)
CSS = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]

CHART_PATHS = {
    "/": {"name": "Index", "view": display_index},
    "/marketing": {"name": "Marketing", "view": display_marketing},
    "/engineering": {"name": "Engineering", "view": display_engineering},
}


LOG.info("Starting server.")
app = dash.Dash(__name__, external_stylesheets=CSS)

div_list = []
# represents the URL bar, doesn't render anything
div_list.append(dcc.Location(id="url", refresh=False))

for key, value in CHART_PATHS.items():
    div_list.append(dcc.Link(value.get("name", "Missing Link Name"), href=Config.APP_URL_PREFIX + key))
    div_list.append(html.Br())

# content will be rendered in this element
div_list.append(html.Div(id="page-content"))
app.layout = html.Div(div_list)


@app.callback(
    dash.dependencies.Output("page-content", "children"), [dash.dependencies.Input("url", "pathname")],
)
def display_page(pathname):
    LOG.info(f"Hitting path {pathname}.")
    if pathname and Config.APP_URL_PREFIX in pathname:
        pathname = re.sub(Config.APP_URL_PREFIX, "", pathname)
    view = CHART_PATHS.get(pathname, {}).get("view")
    if view:
        return view()
    else:
        return html.Div([html.H3(f"Unknown page {Config.APP_URL_PREFIX}{pathname}")])


app.run_server(debug=True, host=Config.APP_HOST, port=Config.APP_PORT)
