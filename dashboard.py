import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dash.dependencies import Input, Output

# Load data
forecast = pd.read_csv("forecast_data.csv")
product_associations = pd.read_csv("product_associations.csv")
df = pd.read_csv(r"Dataset\Walmart.csv")

# Convert dates
forecast['ds'] = pd.to_datetime(forecast['ds'])
df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')

# Create additional metrics
total_sales = forecast['yhat'].sum()
average_lift = product_associations['lift'].mean()
high_risk_alerts = forecast[forecast['yhat'] > forecast['Reorder_Point']].shape[0]

# Initialize Dash app with Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

# Custom CSS styles
CUSTOM_STYLE = {
    "padding": "2rem",
    "backgroundColor": "#f8f9fa",
    "boxShadow": "0 4px 6px rgba(0,0,0,0.1)"
}

# App layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col(html.H1("Walmart Inventory Intelligence Dashboard", 
                       className="text-center mb-4",
                       style={'color': '#2c3e50'}), width=12)
    ]),
    
    # KPI Cards
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Total Forecast Sales", className="card-title"),
                html.H3(f"${total_sales/1e6:.2f}M", className="card-text")
            ])
        ], style=CUSTOM_STYLE), md=3),
        
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Average Association Lift", className="card-title"),
                html.H3(f"{average_lift:.2f}x", className="card-text")
            ])
        ], style=CUSTOM_STYLE), md=3),
        
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Restock Alerts", className="card-title"),
                html.H3(high_risk_alerts, className="card-text text-danger")
            ])
        ], style=CUSTOM_STYLE), md=3),
        
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Stores Analyzed", className="card-title"),
                html.H3(df['Store'].nunique(), className="card-text")
            ])
        ], style=CUSTOM_STYLE), md=3)
    ], className="mb-4"),
    
    # Filters and Main Charts
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Filters", className="card-title"),
                    html.Label("Date Range:"),
                    dcc.DatePickerRange(
                        id='date-picker',
                        start_date=forecast['ds'].min(),
                        end_date=forecast['ds'].max(),
                        display_format='YYYY-MM-DD'
                    ),
                    html.Br(),
                    html.Label("Store Selection:"),
                    dcc.Dropdown(
                        id='store-selector',
                        options=[{'label': f'Store {i}', 'value': i} 
                                for i in df['Store'].unique()],
                        multi=True,
                        value=[1]
                    )
                ])
            ], style=CUSTOM_STYLE)
        ], md=3),
        
        dbc.Col([
            dbc.Tabs([
                dbc.Tab(
                    dcc.Graph(id='forecast-chart'),
                    label="Sales Forecast",
                    tabClassName="mr-1"
                ),
                dbc.Tab(
                    dcc.Graph(id='scatter-plot'),
                    label="Sales Drivers",
                    tabClassName="mr-1"
                )
            ])
        ], md=9)
    ], className="mb-4"),
    
    # Bottom Row
    dbc.Row([
        dbc.Col(dbc.Card(dcc.Graph(id='heatmap')), md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Restock Alerts", className="card-title"),
                    dash_table.DataTable(
                        id='alerts-table',
                        columns=[
                            {'name': 'Date', 'id': 'ds'},
                            {'name': 'Forecast', 'id': 'yhat'},
                            {'name': 'Reorder Point', 'id': 'Reorder_Point'}
                        ],
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left'},
                        filter_action="native",
                        sort_action="native",
                        page_size=10
                    )
                ])
            ])
        ], md=6)
    ]),
    
    # Hidden Div for intermediate storage
    html.Div(id='intermediate-data', style={'display': 'none'})
], fluid=True)

# Callbacks for interactivity
@app.callback(
    Output('intermediate-data', 'children'),
    [Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date'),
     Input('store-selector', 'value')]
)
def update_data(start_date, end_date, selected_stores):
    filtered_forecast = forecast[
        (forecast['ds'] >= start_date) & 
        (forecast['ds'] <= end_date)
    ]
    
    filtered_associations = product_associations[
        product_associations['Store'].isin(selected_stores)
    ]
    
    return {
        'forecast': filtered_forecast.to_json(date_format='iso'),
        'associations': filtered_associations.to_json()
    }

@app.callback(
    [Output('forecast-chart', 'figure'),
     Output('heatmap', 'figure'),
     Output('scatter-plot', 'figure'),
     Output('alerts-table', 'data')],
    [Input('intermediate-data', 'children')]
)
def update_charts(json_data):
    data = json_data
    filtered_forecast = pd.read_json(data['forecast'])
    filtered_associations = pd.read_json(data['associations'])
    
    # Forecast Chart
    forecast_fig = px.line(
        filtered_forecast,
        x='ds',
        y='yhat',
        title='Sales Forecast vs Time',
        template='plotly_white'
    )
    forecast_fig.add_hline(
        y=filtered_forecast['Reorder_Point'].mean(),
        line_dash="dash",
        line_color="red",
        annotation_text="Reorder Point"
    )
    
    # Heatmap
    heatmap_fig = px.imshow(
        filtered_associations.pivot_table(
            index='antecedents',
            columns='consequents',
            values='lift'
        ),
        title='Product Associations Heatmap',
        color_continuous_scale='Blues'
    )
    
    # Scatter Plot
    scatter_fig = px.scatter(
        df,
        x='Unemployment',
        y='Weekly_Sales',
        color='Holiday_Flag',
        size='Temperature',
        hover_data=['Store', 'Fuel_Price'],
        title='Sales Drivers Analysis'
    )
    
    # Alerts Table
    alerts_data = filtered_forecast[filtered_forecast['yhat'] > filtered_forecast['Reorder_Point']]
    alerts_data = alerts_data[['ds', 'yhat', 'Reorder_Point']].to_dict('records')
    
    return forecast_fig, heatmap_fig, scatter_fig, alerts_data

# Run the app
if __name__ == '__main__':
    app.run_server(debug=False, port=8050)