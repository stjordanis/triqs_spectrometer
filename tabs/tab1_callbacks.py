import numpy as np
import dash
import plotly.express as px
import plotly.graph_objects as go
import ast
import inspect

from load_data import load_config, load_w90_hr
from tabs.id_factory import id_factory

def register_callbacks(app, data):
    id = id_factory('tab1')

    @app.callback(
        dash.dependencies.Output(id('data-storage'), 'data'),
        [dash.dependencies.Input(id('data-storage'), 'data'),
         dash.dependencies.Input(id('upload-file'), 'contents'),
         dash.dependencies.Input(id('upload-file'), 'filename'),
         dash.dependencies.Input(id('upload-w90'), 'contents')])
    def update_data(data,config_contents,config_filename, w90_contents):  

        if config_filename != None and not config_filename == data['config_filename']:
            print('loading config file from h5...')
            data = load_config(config_contents, config_filename)

        if w90_contents != None:
            print('loading w90 hr file...')

            load_w90_hr(w90_contents)

        return data

    @app.callback(
        dash.dependencies.Output(id('k-points'), 'data'),
        dash.dependencies.Input(id('add-kpoint'), 'n_clicks'),
        dash.dependencies.State(id('k-points'), 'data'),
        dash.dependencies.State(id('k-points'), 'columns'))
    def add_row(n_clicks, rows, columns):
        if n_clicks > 0:
            rows.append({c['id']: '' for c in columns})
        return rows
    
    @app.callback(
         [dash.dependencies.Output(id('sigma-function'), 'style'),
         dash.dependencies.Output(id('sigma-upload'), 'style')],
        dash.dependencies.Input(id('choose-sigma'), 'value')
        )
    def toggle_update_sigma(sigma_radio_item):
        if sigma_radio_item == 'upload':
            return [{'display': 'none'}] * 1 + [{'display': 'block'}]
        else:
            return [{'display': 'block'}] * 1 + [{'display': 'none'}]

    @app.callback(
        #[dash.dependencies.Output('sigma-function-output', 'children'),
        # dash.dependencies.Output('sigma-function', 'sigma')],
        dash.dependencies.Output(id('sigma-function-output'), 'children'),
        dash.dependencies.Input(id('sigma-function-button'), 'n_clicks'),
        dash.dependencies.State(id('sigma-function-input'), 'value')
        )
    def update_sigma(n_clicks, value):
        if n_clicks > 0:
            # parse function
            tree = ast.parse(value, mode='exec')
            code = compile(tree, filename='test', mode='exec')
            namespace = {} 
            exec(code, namespace)

            return 'You have entered: \n{}'.format(value)

    @app.callback(
        dash.dependencies.Output(id('colorscale'), 'options'),
        dash.dependencies.Input(id('colorscale-mode'), 'value')
        )
    def update_colorscales(mode):
        colorscales = [name for name, body in inspect.getmembers(getattr(px.colors, mode))
                if isinstance(body, list) and len(name.rsplit('_')) == 1]
        return [{'label': key, 'value': key} for key in colorscales]

    # make connections
    @app.callback(
        dash.dependencies.Output('Akw', 'figure'),
        [dash.dependencies.Input(id('tb-bands'), 'on'),
         dash.dependencies.Input(id('akw'), 'on'),
         dash.dependencies.Input(id('colorscale'), 'value'),
         dash.dependencies.Input(id('data-storage'), 'data')])
    #
    def update_Akw(tb_bands, akw, colorscale, data):
        layout = go.Layout()
        fig = go.Figure(layout=layout)
    
        fig.add_shape(type = 'line', x0=0, y0=0, x1=max(data['k_mesh']), y1=0, line=dict(color='gray', width=0.8))
    
        if akw:
            # kw_x, kw_y = np.meshgrid(data.tb_data['k_mesh'], w_mesh['w_mesh'])
            z_data = np.log(np.array(data['Akw']).T)
            fig.add_trace(go.Heatmap(x=data['k_mesh'], y=data['freq_mesh'], z=z_data,
                          colorscale=colorscale,reversescale=False, showscale=False,
                          zmin=np.min(z_data), zmax=np.max(z_data)))
    
    
        if tb_bands:
            for band in range(len(data['eps_nuk'])):
                fig.add_trace(go.Scattergl(x=data['k_mesh'], y=data['eps_nuk'][band], mode='lines',
                              line=go.scattergl.Line(color=px.colors.sequential.Viridis[0]), showlegend=False, text=f'tb band {band}',
                              hoverinfo='x+y+text'
                              ))
        fig.update_layout(margin={'l': 40, 'b': 40, 't': 10, 'r': 40},
                          clickmode='event+select',
                          hovermode='closest',
                          yaxis_range=[data['freq_mesh'][0], data['freq_mesh'][-1]],
                          yaxis_title='ω (eV)',
                          xaxis=dict(ticktext=['γ' if k == 'g' else k for k in data['k_points_labels']],tickvals=data['k_points']),
                          font=dict(size=16))
    
        fig.update_xaxes(showspikes=True, spikemode='across', spikesnap='cursor', rangeslider_visible=False, 
                         showticklabels=True, spikedash='solid')
        fig.update_yaxes(showspikes=True, spikemode='across', spikesnap='cursor', showticklabels=True, spikedash='solid')
        fig.update_traces(xaxis='x', hoverinfo='none')
    
        return fig
    
    
    @app.callback(
        [dash.dependencies.Output('EDC', 'figure'),
        dash.dependencies.Output('kpt_edc', 'value'),
        dash.dependencies.Output('kpt_edc', 'max')],
        [dash.dependencies.Input('kpt_edc', 'value'),
        dash.dependencies.Input(id('data-storage'), 'data'),
        dash.dependencies.Input('Akw', 'clickData')]
        )
    #
    def update_EDC(kpt_edc, data, click_coordinates):
        layout = go.Layout()
        fig = go.Figure(layout=layout)
        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == 'Akw':
            new_kpt = click_coordinates['points'][0]['x']
            kpt_edc = np.argmin(np.abs(np.array(data['k_mesh']) - new_kpt))
        
        fig.add_trace(go.Scattergl(x=data['freq_mesh'], y=np.array(data['Akw'])[kpt_edc,:], mode='lines',
            line=go.scattergl.Line(color=px.colors.sequential.Viridis[0]), showlegend=True, name='k = {:.3f}'.format(data['k_mesh'][kpt_edc]),
                              hoverinfo='x+y+text'
                              ))
    
        fig.update_layout(margin={'l': 40, 'b': 40, 't': 10, 'r': 40},
                          hovermode='closest',
                          xaxis_range=[data['freq_mesh'][0], data['freq_mesh'][-1]],
                          yaxis_range=[0, data['max_Akw']],
                          xaxis_title='ω (eV)',
                          yaxis_title='A(ω)',
                          font=dict(size=16),
                          legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                          )
        return fig, kpt_edc, len(data['k_mesh'])-1
    
    @app.callback(
        [dash.dependencies.Output('MDC', 'figure'),
        dash.dependencies.Output('w_mdc', 'value'),
        dash.dependencies.Output('w_mdc', 'max')],
        [dash.dependencies.Input('w_mdc', 'value'),
         dash.dependencies.Input(id('data-storage'), 'data'),
         dash.dependencies.Input('Akw', 'clickData')]
        )
    #
    def update_MDC(w_mdc, data, click_coordinates):
        layout = go.Layout()
        fig = go.Figure(layout=layout)
        ctx = dash.callback_context
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == 'Akw':
            new_w = click_coordinates['points'][0]['y']
            w_mdc = np.argmin(np.abs(np.array(data['freq_mesh']) - new_w))
    
        fig.add_trace(go.Scattergl(x=data['k_mesh'], y=np.array(data['Akw'])[:, w_mdc], mode='lines',
            line=go.scattergl.Line(color=px.colors.sequential.Viridis[0]), showlegend=True, name='ω = {:.3f} eV'.format(data['freq_mesh'][w_mdc]),
                              hoverinfo='x+y+text'
                              ))
    
        fig.update_layout(margin={'l': 40, 'b': 40, 't': 10, 'r': 40},
                          hovermode='closest',
                          xaxis_range=[data['k_mesh'][0], data['k_mesh'][-1]],
                        #   yaxis_range=[0, 1.05 * np.max(np.array(data['Akw'])[:, w_mdc])],
                          yaxis_range=[0, data['max_Akw']],
                          xaxis_title='k',
                          yaxis_title='A(k)',
                          font=dict(size=16),
                          xaxis=dict(ticktext=['γ' if k == 'g' else k for k in data['k_points_labels']],tickvals=data['k_points']),
                          legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                          )
        return fig, w_mdc, len(data['freq_mesh'])-1


