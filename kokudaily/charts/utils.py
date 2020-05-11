import dash_html_components as html


def generate_table(columns, rows):
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(col) for col in columns])),
            html.Tbody(
                [
                    html.Tr([html.Td(str(rows[i][col])) for col in columns])
                    for i in range(len(rows))
                ]
            ),
        ]
    )
