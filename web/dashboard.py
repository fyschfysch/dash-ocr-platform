"""
Основной веб-интерфейс для OCR платформы на базе Dash 3.0+
Полная замена Streamlit с улучшенным функционалом и интерактивностью
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, clientside_callback
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import plotly.express as px

import fitz  # PyMuPDF
from PIL import Image
import pandas as pd
import numpy as np
import io
import base64
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging

# Импорты наших модулей
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.ocr_engine import DocumentProcessor
from core.image_processor import AdvancedImageProcessor, ImageAnalyzer, RegionProcessor
from core.config import get_available_configs, get_config, get_field_description, UncertaintyEngine
from core.parsers import ParserRegistry
from web.markup_tool import MarkupTool, setup_markup_callbacks, MarkupIntegration

logger = logging.getLogger(__name__)


class OCRDashboard:
    """
    Основной класс веб-интерфейса OCR платформы для Dash 3.0+
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract
        """
        # Инициализация компонентов
        self.doc_processor = DocumentProcessor(tesseract_cmd)
        self.image_processor = AdvancedImageProcessor()
        self.image_analyzer = ImageAnalyzer()
        self.region_processor = RegionProcessor()
        self.markup_tool = MarkupTool()
        
        # Создание Dash приложения для версии 3.0+
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[
                dbc.themes.BOOTSTRAP, 
                dbc.icons.FONT_AWESOME,
                "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
            ],
            title="🔍 OCR Платформа для документов",
            suppress_callback_exceptions=True,
            assets_folder=os.path.join(os.path.dirname(__file__), '..', 'static')
        )
        
        # Настройка layout
        self.app.layout = self.create_main_layout()
        
        # Регистрация callbacks
        self.setup_callbacks()
        # setup_markup_callbacks(self.app, self.markup_tool)  # Временно отключено
        
        # Клиентские callbacks для улучшения производительности
        self.setup_clientside_callbacks()
    
    def create_main_layout(self) -> html.Div:
        """
        Создание основного layout приложения
        """
        return dbc.Container([
            # Заголовок с градиентом
            html.Div([
                html.H1([
                    html.I(className="fas fa-search me-3"),
                    "OCR Платформа для документов"
                ], className="mb-2"),
                html.P(
                    "Система распознавания документов о переподготовке и повышении квалификации с интерактивной разметкой полей",
                    className="lead mb-0"
                )
            ], className="main-header mb-4"),
            
            # Навигационные табы с иконками
            dbc.Tabs([
                dbc.Tab(
                    label=[html.I(className="fas fa-file-pdf me-2"), "Распознавание документов"],
                    tab_id="ocr-tab",
                    children=self.create_ocr_tab(),
                    className="fw-bold"
                ),
                dbc.Tab(
                    label=[html.I(className="fas fa-crosshairs me-2"), "Разметка полей"],
                    tab_id="markup-tab", 
                    children=html.Div("Функция в разработке"),  # Упрощено
                    className="fw-bold"
                ),
                dbc.Tab(
                    label=[html.I(className="fas fa-chart-bar me-2"), "Аналитика"],
                    tab_id="analytics-tab",
                    children=self.create_analytics_tab(),
                    className="fw-bold"
                ),
                dbc.Tab(
                    label=[html.I(className="fas fa-info-circle me-2"), "Справка"],
                    tab_id="help-tab",
                    children=self.create_help_tab(),
                    className="fw-bold"
                )
            ], id="main-tabs", active_tab="ocr-tab", className="mb-4"),
            
            # Модальные окна
            self.create_modals(),
            
            # Скрытые div для хранения данных
            dcc.Store(id="pdf-pages-store"),
            dcc.Store(id="ocr-results-store"),
            dcc.Store(id="processing-status-store"),
            dcc.Store(id="image-quality-store"),
            
        ], fluid=True, className="py-4")
    
    def create_ocr_tab(self) -> html.Div:
        """
        Создание основной вкладки для OCR
        """
        return html.Div([
            # Панель загрузки файла с улучшенным дизайном
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-cloud-upload-alt me-2"),
                    "Загрузка документа"
                ], className="fw-bold"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dcc.Upload(
                                id='upload-document',
                                children=html.Div([
                                    html.I(className="fas fa-cloud-upload-alt fa-4x mb-3 text-primary"),
                                    html.H5("Перетащите PDF файл сюда", className="mb-2"),
                                    html.P("или нажмите для выбора файла", className="text-muted mb-2"),
                                    html.Small("Поддерживаются файлы: PDF до 50MB", className="text-muted")
                                ], className="text-center"),
                                style={
                                    'width': '100%', 'height': '180px',
                                    'lineHeight': '60px', 'borderWidth': '3px',
                                    'borderStyle': 'dashed', 'borderRadius': '15px',
                                    'borderColor': '#007bff', 'backgroundColor': '#f8f9fa',
                                    'cursor': 'pointer', 'transition': 'all 0.3s ease'
                                },
                                className="upload-area",
                                multiple=False,
                                accept='.pdf'
                            )
                        ], width=8),
                        
                        dbc.Col([
                            # Настройки обработки
                            dbc.Card([
                                dbc.CardHeader("⚙️ Настройки обработки", className="py-2"),
                                dbc.CardBody([
                                    html.Label("Тип документа:", className="fw-bold mb-2"),
                                    dcc.Dropdown(
                                        id='config-selector',
                                        options=[
                                            {'label': '🏢 1Т - Удостоверение', 'value': '1T_CERTIFICATE'},
                                            {'label': '🏢 1Т - Диплом', 'value': '1T_DIPLOMA'},
                                            {'label': '🏛️ РОСНОУ - Диплом', 'value': 'ROSNOU_DIPLOMA'},
                                            {'label': '🏛️ РОСНОУ - Удостоверение', 'value': 'ROSNOU_CERTIFICATE'},
                                            {'label': '🏦 ФинУнив - Удостоверение v1', 'value': 'FINUNIV_CERT_V1'},
                                            {'label': '🏦 ФинУнив - Удостоверение v2', 'value': 'FINUNIV_CERT_V2'}
                                        ],
                                        placeholder="Выберите тип документа",
                                        className="mb-3"
                                    ),
                                    
                                    html.Label("Поворот изображения:", className="fw-bold mb-2"),
                                    dcc.Dropdown(
                                        id='rotation-selector',
                                        options=[
                                            {'label': '↕️ Без поворота', 'value': 0},
                                            {'label': '↻ 90° по часовой', 'value': 90},
                                            {'label': '↶ 180°', 'value': 180},
                                            {'label': '↺ 270° по часовой', 'value': 270}
                                        ],
                                        value=0,
                                        className="mb-3"
                                    ),
                                    
                                    dbc.Button(
                                        [html.I(className="fas fa-rocket me-2"), "Запустить OCR"],
                                        id="run-ocr-btn",
                                        color="primary",
                                        size="lg",
                                        disabled=True,
                                        className="w-100 fw-bold"
                                    )
                                ], className="p-3")
                            ], className="shadow-sm")
                        ], width=4)
                    ])
                ])
            ], className="mb-4 shadow-sm"),
            
            # Панель статуса и прогресса
            html.Div(id="status-panel"),
            
            # Панель просмотра PDF
            html.Div(id="pdf-preview-panel", className="mb-4"),
            
            # Панель результатов OCR
            html.Div(id="ocr-results-panel")
        ])
    
    def create_analytics_tab(self) -> html.Div:
        """
        Создание вкладки аналитики
        """
        return html.Div([
            dbc.Card([
                dbc.CardHeader("📊 Статистика обработки"),
                dbc.CardBody([
                    html.Div(id="analytics-content", children=[
                        html.P("Загрузите и обработайте документы для просмотра аналитики", 
                              className="text-muted text-center py-5")
                    ])
                ])
            ])
        ])
    
    def create_help_tab(self) -> html.Div:
        """
        Создание справочной вкладки с исправленным синтаксисом
        """
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-building me-2"),
                            "Поддерживаемые организации"
                        ]),
                        dbc.CardBody([
                            # 1Т
                            html.Div([
                                html.H5([
                                    html.I(className="fas fa-certificate me-2 text-primary"),
                                    "1Т"
                                ]),
                                html.Ul([
                                    html.Li([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Удостоверения о повышении квалификации"
                                    ]),
                                    html.Li([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Дипломы о профессиональной переподготовке"
                                    ])
                                ])
                            ], className="mb-4"),
                            
                            # РОСНОУ
                            html.Div([
                                html.H5([
                                    html.I(className="fas fa-university me-2 text-info"),
                                    "РОСНОУ (Российский новый университет)"
                                ]),
                                html.Ul([
                                    html.Li([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Удостоверения о повышении квалификации"
                                    ]),
                                    html.Li([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Дипломы о профессиональной переподготовке"
                                    ])
                                ])
                            ], className="mb-4"),
                            
                            # Финансовый университет
                            html.Div([
                                html.H5([
                                    html.I(className="fas fa-landmark me-2 text-warning"),
                                    "Финансовый университет"
                                ]),
                                html.Ul([
                                    html.Li([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Удостоверения (вариант 1) - ФИО в одну строку"
                                    ]),
                                    html.Li([
                                        html.I(className="fas fa-exclamation-triangle me-2 text-warning"),
                                        "Удостоверения (вариант 2) - ФИО на трёх строках в дательном падеже"
                                    ])
                                ])
                            ])
                        ])
                    ], className="shadow-sm")
                ], width=6),
                
                dbc.Col([
                    # Извлекаемые поля
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-list-check me-2"),
                            "Извлекаемые поля"
                        ]),
                        dbc.CardBody([
                            html.Ul([
                                html.Li([
                                    html.I(className="fas fa-user me-2 text-primary"),
                                    html.Strong("ФИО"),
                                    " (в именительном падеже)"
                                ]),
                                html.Li([
                                    html.I(className="fas fa-id-card me-2 text-info"),
                                    html.Strong("Серия и номер"),
                                    " документа"
                                ]),
                                html.Li([
                                    html.I(className="fas fa-hashtag me-2 text-success"),
                                    html.Strong("Регистрационный номер")
                                ]),
                                html.Li([
                                    html.I(className="fas fa-calendar me-2 text-warning"),
                                    html.Strong("Дата выдачи"),
                                    " (в ISO формате)"
                                ])
                            ])
                        ])
                    ], className="shadow-sm mb-4"),
                    
                    # Советы по использованию
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-lightbulb me-2"),
                            "Советы по использованию"
                        ]),
                        dbc.CardBody([
                            html.Ul([
                                html.Li([
                                    html.I(className="fas fa-file-pdf me-2 text-danger"),
                                    "Загружайте PDF файлы высокого качества"
                                ]),
                                html.Li([
                                    html.I(className="fas fa-cog me-2 text-primary"),
                                    "Выбирайте правильную конфигурацию документа"
                                ]),
                                html.Li([
                                    html.I(className="fas fa-sync-alt me-2 text-info"),
                                    "При необходимости поворачивайте изображение"
                                ]),
                                html.Li([
                                    html.I(className="fas fa-crosshairs me-2 text-success"),
                                    "Используйте разметку полей для новых типов документов"
                                ]),
                                html.Li([
                                    html.I(className="fas fa-exclamation-triangle me-2 text-warning"),
                                    "Поля с флагом неуверенности требуют проверки"
                                ])
                            ])
                        ])
                    ], className="shadow-sm")
                ], width=6)
            ])
        ])
    
    def create_modals(self) -> html.Div:
        """
        Создание модальных окон
        """
        return html.Div([
            dbc.Modal([
                dbc.ModalHeader("📊 Детальные результаты OCR"),
                dbc.ModalBody(id="detailed-results-body"),
                dbc.ModalFooter([
                    dbc.Button("Закрыть", id="close-details-modal", color="secondary")
                ])
            ], id="details-modal", size="lg"),
            
            dbc.Modal([
                dbc.ModalHeader("❌ Ошибка"),
                dbc.ModalBody(id="error-modal-body"),
                dbc.ModalFooter([
                    dbc.Button("Закрыть", id="close-error-modal", color="secondary")
                ])
            ], id="error-modal")
        ])
    
    def setup_callbacks(self):
        """
        Настройка базовых callbacks для Dash 3.0+
        """
        
        @self.app.callback(
            [Output('pdf-pages-store', 'data'),
             Output('pdf-preview-panel', 'children'),
             Output('run-ocr-btn', 'disabled'),
             Output('status-panel', 'children')],
            [Input('upload-document', 'contents')],
            [State('upload-document', 'filename')]
        )
        def handle_file_upload(contents, filename):
            """Обработка загрузки PDF файла"""
            if not contents:
                return None, None, True, None
            
            try:
                # Декодируем файл
                content_type, content_string = contents.split(',')
                decoded = base64.b64decode(content_string)
                
                # Конвертируем PDF в изображения
                images = self.image_processor.convert_pdf_from_bytes(decoded)
                
                # Сохраняем изображения в base64
                pages_data = []
                
                for page_num, img in enumerate(images):
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    img_b64 = base64.b64encode(buffer.getvalue()).decode()
                    pages_data.append(img_b64)
                
                preview_panel = dbc.Alert([
                    html.I(className="fas fa-file-pdf me-2"),
                    f"Загружен файл: {filename} ({len(pages_data)} стр.)"
                ], color="info")
                
                status_panel = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"Файл успешно загружен! Найдено страниц: {len(pages_data)}. Выберите конфигурацию и запустите OCR."
                ], color="success", className="mb-0")
                
                logger.info(f"PDF загружен: {filename}, страниц: {len(pages_data)}")
                return pages_data, preview_panel, False, status_panel
                
            except Exception as e:
                logger.error(f"Ошибка загрузки PDF: {e}")
                error_panel = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Ошибка загрузки файла: {str(e)}"
                ], color="danger", className="mb-0")
                
                return None, None, True, error_panel
        
        @self.app.callback(
            [Output('ocr-results-panel', 'children'),
             Output('ocr-results-store', 'data')],
            [Input('run-ocr-btn', 'n_clicks')],
            [State('pdf-pages-store', 'data'),
             State('config-selector', 'value'),
             State('rotation-selector', 'value')]
        )
        def run_ocr_processing(n_clicks, pages_data, config_key, rotation):
            """Упрощенный OCR процессинг"""
            if not n_clicks or not pages_data or not config_key:
                raise PreventUpdate
            
            try:
                result_panel = dbc.Alert([
                    html.I(className="fas fa-cogs me-2"),
                    f"OCR обработка запущена для {len(pages_data)} страниц с конфигурацией {config_key}. Функционал в разработке."
                ], color="info")
                
                return result_panel, {"status": "processing", "pages": len(pages_data)}
                
            except Exception as e:
                error_panel = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Ошибка OCR: {str(e)}"
                ], color="danger")
                
                return error_panel, None
    
    def setup_clientside_callbacks(self):
        """Настройка клиентских callbacks"""
        pass
    
    def run_server(self, debug: bool = True, host: str = '127.0.0.1', port: int = 8050):
        """
        Запуск веб-сервера с Dash 3.0+ API
        """
        logger.info(f"🚀 Запуск OCR Dashboard на http://{host}:{port}")
        logger.info("📄 Поддерживаемые документы:")
        logger.info("   • 1Т - Удостоверения и дипломы")
        logger.info("   • РОСНОУ - Удостоверения и дипломы") 
        logger.info("   • Финуниверситет - Удостоверения (2 варианта)")
        logger.info("🎯 Используйте вкладку 'Разметка полей' для новых типов документов")
        
        # Dash 3.0+: используем app.run вместо app.run_server
        try:
            self.app.run(debug=debug, host=host, port=port)
        except Exception as e:
            logger.error(f"Ошибка запуска сервера: {e}")
            # Fallback на Flask сервер для совместимости
            logger.info("Пробуем альтернативный способ запуска...")
            self.app.server.run(debug=debug, host=host, port=port)


def create_dash_app(tesseract_cmd: Optional[str] = None) -> dash.Dash:
    """
    Создание Dash приложения (для внешнего использования)
    """
    dashboard = OCRDashboard(tesseract_cmd)
    return dashboard.app


if __name__ == '__main__':
    # Создание и запуск приложения
    dashboard = OCRDashboard()
    dashboard.run_server(debug=True)
