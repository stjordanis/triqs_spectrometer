import dash_core_components as dcc
import dash_html_components as html

from tabs.dashboard import make_dashboard

def layout(data):
    return dcc.Tab(
        label='Raman spectroscopy',
        children=[
            # column 1
            make_dashboard(data, 4),
            # column 2
            html.Div([
                html.H1('Page under construction 🚧'),
                ],
                style={
                    'display': 'inline-block',
                    'width': '84%',
                    'textAlign': 'center',
                    'margin-top': '40%'
                    }
                )
            ]
        )
