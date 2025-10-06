import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

# Простейшее Dash приложение для тестирования
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP]
)

app.layout = dbc.Container([
    dbc.Alert("Тест Dash Bootstrap Components", color="primary"),
    
    dbc.Card([
        dbc.CardHeader("Заголовок карты"),
        dbc.CardBody([
            html.H4("Это работает!"),
            html.P("Bootstrap компоненты загружены правильно.")
        ])
    ]),
    
    dbc.Button("Тестовая кнопка", color="success", className="mt-3")
])

if __name__ == '__main__':
    app.run(debug=True, port=8051)  # Другой порт для теста
