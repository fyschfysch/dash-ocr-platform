"""
Упрощенная версия OCR Dashboard для отладки
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import logging

logger = logging.getLogger(__name__)


class OCRDashboard:
    """
    Упрощенная версия OCR Dashboard
    """
    
    def __init__(self, tesseract_cmd=None):
        """Инициализация с минимальными компонентами"""
        
        # Создание Dash приложения
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[
                dbc.themes.BOOTSTRAP,
                dbc.icons.FONT_AWESOME
            ],
            title="OCR Платформа"
        )
        
        # Простой layout
        self.app.layout = self.create_layout()
        
        # Базовые callbacks
        self.setup_callbacks()
    
    def create_layout(self):
        """Создание простого layout"""
        return dbc.Container([
            # Заголовок
            dbc.Alert([
                html.H1([
                    html.I(className="fas fa-search me-3"),
                    "OCR Платформа для документов"
                ]),
                html.P("Система распознавания документов", className="mb-0")
            ], color="primary", className="mb-4"),
            
            # Основная панель
            dbc.Card([
                dbc.CardHeader("📤 Загрузка документа"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            # Область загрузки файла
                            dcc.Upload(
                                id='upload-document',
                                children=dbc.Alert([
                                    html.I(className="fas fa-cloud-upload-alt fa-3x mb-3"),
                                    html.Br(),
                                    "Перетащите PDF файл сюда или нажмите для выбора"
                                ], color="light", className="text-center"),
                                style={
                                    'width': '100%',
                                    'borderWidth': '2px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '10px',
                                    'borderColor': '#007bff',
                                    'cursor': 'pointer'
                                },
                                multiple=False,
                                accept='.pdf'
                            )
                        ], width=8),
                        
                        dbc.Col([
                            # Настройки
                            html.Label("Тип документа:", className="fw-bold"),
                            dcc.Dropdown(
                                id='config-selector',
                                options=[
                                    {'label': '1Т - Удостоверение', 'value': '1T_CERTIFICATE'},
                                    {'label': '1Т - Диплом', 'value': '1T_DIPLOMA'},
                                    {'label': 'РОСНОУ - Диплом', 'value': 'ROSNOU_DIPLOMA'}
                                ],
                                placeholder="Выберите тип",
                                className="mb-3"
                            ),
                            
                            dbc.Button(
                                "🚀 Запустить OCR",
                                id="run-ocr-btn",
                                color="primary",
                                size="lg",
                                disabled=True,
                                className="w-100"
                            )
                        ], width=4)
                    ])
                ])
            ], className="mb-4"),
            
            # Панель статуса
            html.Div(id="status-panel"),
            
            # Результаты
            html.Div(id="results-panel")
            
        ], fluid=True, className="py-4")
    
    def setup_callbacks(self):
        """Базовые callbacks"""
        
        @self.app.callback(
            [Output('run-ocr-btn', 'disabled'),
             Output('status-panel', 'children')],
            [Input('upload-document', 'contents')],
            [State('upload-document', 'filename')]
        )
        def handle_upload(contents, filename):
            """Обработка загрузки файла"""
            if not contents:
                return True, ""
            
            status = dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"Файл загружен: {filename}"
            ], color="success")
            
            return False, status
        
        @self.app.callback(
            Output('results-panel', 'children'),
            [Input('run-ocr-btn', 'n_clicks')],
            [State('config-selector', 'value')]
        )
        def run_ocr(n_clicks, config):
            """Имитация OCR"""
            if not n_clicks or not config:
                raise PreventUpdate
            
            return dbc.Alert([
                html.I(className="fas fa-cogs me-2"),
                f"OCR запущен с конфигурацией: {config}"
            ], color="info")
    
    def run_server(self, debug=True, host='127.0.0.1', port=8050):
        """Запуск сервера"""
        logger.info(f"🚀 Запуск на http://{host}:{port}")
        try:
            self.app.run(debug=debug, host=host, port=port)
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")
            self.app.server.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    dashboard = OCRDashboard()
    dashboard.run_server(debug=True)
