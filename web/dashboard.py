"""
Основной веб-интерфейс для OCR платформы на базе Dash
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
    Основной класс веб-интерфейса OCR платформы
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
        
        # Создание Dash приложения
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
        setup_markup_callbacks(self.app, self.markup_tool)
        
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
                    children=self.markup_tool.create_markup_layout(),
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
            
            # Интервал для обновления прогресса
            dcc.Interval(id="progress-interval", interval=1000, disabled=True),
            
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
                                    
                                    # Дополнительные настройки
                                    dbc.Accordion([
                                        dbc.AccordionItem([
                                            dbc.Row([
                                                dbc.Col([
                                                    dbc.Checklist(
                                                        id="advanced-options",
                                                        options=[
                                                            {"label": "Улучшение качества", "value": "enhance"},
                                                            {"label": "Удаление шума", "value": "denoise"},
                                                            {"label": "Коррекция наклона", "value": "deskew"},
                                                            {"label": "Агрессивная обработка", "value": "aggressive"}
                                                        ],
                                                        value=["enhance"],
                                                        inline=False
                                                    )
                                                ])
                                            ])
                                        ], title="🔧 Дополнительные настройки")
                                    ], start_collapsed=True, className="mb-3"),
                                    
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
            
            # Панель анализа качества изображения
            html.Div(id="quality-analysis-panel", className="mb-4"),
            
            # Панель результатов OCR
            html.Div(id="ocr-results-panel")
        ])
    
    def create_analytics_tab(self) -> html.Div:
        """
        Создание вкладки аналитики
        """
        return html.Div([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("📊 Статистика обработки"),
                        dbc.CardBody([
                            html.Div(id="analytics-content", children=[
                                html.P("Загрузите и обработайте документы для просмотра аналитики", 
                                      className="text-muted text-center py-5")
                            ])
                        ])
                    ])
                ], width=12)
            ])
        ])
    
    def create_help_tab(self) -> html.Div:
        """
        Создание справочной вкладки с улучшенным дизайном
        """
        return html.Div([
            dbc.Row([
                dbc.Col([
                    # Поддерживаемые организации
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-building me-2"),
                            "Поддерживаемые организации"
                        ], className="fw-bold"),
                        dbc.CardBody([
                            # 1Т
                            html.Div([
                                html.H5([
                                    html.I(className="fas fa-certificate me-2 text-primary"),
                                    "1Т"
                                ]),
                                dbc.ListGroup([
                                    dbc.ListGroupItem([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Удостоверения о повышении квалификации"
                                    ]),
                                    dbc.ListGroupItem([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Дипломы о профессиональной переподготовке"
                                    ])
                                ], flush=True)
                            ], className="mb-4"),
                            
                            # РОСНОУ
                            html.Div([
                                html.H5([
                                    html.I(className="fas fa-university me-2 text-info"),
                                    "РОСНОУ (Российский новый университет)"
                                ]),
                                dbc.ListGroup([
                                    dbc.ListGroupItem([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Удостоверения о повышении квалификации"
                                    ]),
                                    dbc.ListGroupItem([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Дипломы о профессиональной переподготовке"
                                    ])
                                ], flush=True)
                            ], className="mb-4"),
                            
                            # Финуниверситет
                            html.Div([
                                html.H5([
                                    html.I(className="fas fa-landmark me-2 text-warning"),
                                    "Финансовый университет"
                                ]),
                                dbc.ListGroup([
                                    dbc.ListGroupItem([
                                        html.I(className="fas fa-check-circle me-2 text-success"),
                                        "Удостоверения (вариант 1) - ФИО в одну строку"
                                    ]),
                                    dbc.ListGroupItem([
                                        html.I(className="fas fa-exclamation-triangle me-2 text-warning"),
                                        "Удостоверения (вариант 2) - ФИО на трёх строках в дательном падеже"
                                    ])
                                ], flush=True)
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
                        ], className="fw-bold"),
                        dbc.CardBody([
                            dbc.ListGroup([
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-user me-2 text-primary"),
                                    html.Strong("ФИО"), " (в именительном падеже)"
                                ]),
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-id-card me-2 text-info"),
                                    html.Strong("Серия и номер"), " документа"
                                ]),
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-hashtag me-2 text-success"),
                                    html.Strong("Регистрационный номер")
                                ]),
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-calendar me-2 text-warning"),
                                    html.Strong("Дата выдачи"), " (в ISO формате)"
                                ])
                            ], flush=True)
                        ])
                    ], className="shadow-sm mb-4"),
                    
                    # Советы по использованию
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-lightbulb me-2"),
                            "Советы по использованию"
                        ], className="fw-bold"),
                        dbc.CardBody([
                            dbc.ListGroup([
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-file-pdf me-2 text-danger"),
                                    "Загружайте PDF файлы высокого качества"
                                ]),
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-cog me-2 text-primary"),
                                    "Выбирайте правильную конфигурацию документа"
                                ]),
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-sync-alt me-2 text-info"),
                                    "При необходимости поворачивайте изображение"
                                ]),
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-crosshairs me-2 text-success"),
                                    "Используйте разметку полей для новых типов документов"
                                ]),
                                dbc.ListGroupItem([
                                    html.I(className="fas fa-exclamation-triangle me-2 text-warning"),
                                    "Поля с флагом неуверенности требуют проверки"
                                ])
                            ], flush=True)
                        ])
                    ], className="shadow-sm")
                ], width=6)
            ]),
            
            # Горячие клавиши
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-keyboard me-2"),
                            "Горячие клавиши"
                        ], className="fw-bold"),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Div([
                                        html.Kbd("Ctrl + Enter", className="me-2"),
                                        "Запуск OCR"
                                    ], className="mb-2"),
                                    html.Div([
                                        html.Kbd("Escape", className="me-2"),
                                        "Закрыть модальные окна"
                                    ], className="mb-2")
                                ], width=6),
                                dbc.Col([
                                    html.Div([
                                        html.Kbd("Ctrl + S", className="me-2"),
                                        "Сохранить результаты"
                                    ], className="mb-2"),
                                    html.Div([
                                        html.Kbd("F5", className="me-2"),
                                        "Обновить страницу"
                                    ], className="mb-2")
                                ], width=6)
                            ])
                        ])
                    ], className="shadow-sm")
                ], width=12)
            ], className="mt-4")
        ])
    
    def create_modals(self) -> html.Div:
        """
        Создание модальных окон
        """
        return html.Div([
            # Модальное окно с детальными результатами
            dbc.Modal([
                dbc.ModalHeader([
                    html.I(className="fas fa-chart-line me-2"),
                    "Детальные результаты OCR"
                ]),
                dbc.ModalBody(id="detailed-results-body"),
                dbc.ModalFooter([
                    dbc.Button("Закрыть", id="close-details-modal", color="secondary"),
                    dbc.Button("Экспорт", id="export-details-btn", color="primary")
                ])
            ], id="details-modal", size="xl"),
            
            # Модальное окно настроек
            dbc.Modal([
                dbc.ModalHeader([
                    html.I(className="fas fa-cogs me-2"),
                    "Настройки приложения"
                ]),
                dbc.ModalBody([
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Качество изображения:", className="fw-bold"),
                                dcc.Slider(
                                    id="quality-slider",
                                    min=1, max=5, step=1, value=3,
                                    marks={i: f"{'★' * i}" for i in range(1, 6)}
                                )
                            ], width=6),
                            dbc.Col([
                                html.Label("Максимальный размер:", className="fw-bold"),
                                dbc.Input(
                                    id="max-dimension-input",
                                    type="number",
                                    value=1200,
                                    min=600, max=3000, step=100
                                )
                            ], width=6)
                        ])
                    ])
                ]),
                dbc.ModalFooter([
                    dbc.Button("Отмена", id="cancel-settings-modal", color="secondary"),
                    dbc.Button("Сохранить", id="save-settings-modal", color="primary")
                ])
            ], id="settings-modal"),
            
            # Модальное окно ошибки
            dbc.Modal([
                dbc.ModalHeader([
                    html.I(className="fas fa-exclamation-triangle me-2 text-danger"),
                    "Ошибка обработки"
                ]),
                dbc.ModalBody(id="error-modal-body"),
                dbc.ModalFooter([
                    dbc.Button("Закрыть", id="close-error-modal", color="secondary")
                ])
            ], id="error-modal")
        ])
    
    def setup_callbacks(self):
        """
        Настройка всех callbacks
        """
        
        @self.app.callback(
            [Output('pdf-pages-store', 'data'),
             Output('pdf-preview-panel', 'children'),
             Output('run-ocr-btn', 'disabled'),
             Output('status-panel', 'children'),
             Output('image-quality-store', 'data')],
            [Input('upload-document', 'contents')],
            [State('upload-document', 'filename')]
        )
        def handle_file_upload(contents, filename):
            """Обработка загрузки PDF файла"""
            if not contents:
                return None, None, True, None, None
            
            try:
                # Декодируем файл
                content_type, content_string = contents.split(',')
                decoded = base64.b64decode(content_string)
                
                # Конвертируем PDF в изображения
                images = self.image_processor.convert_pdf_from_bytes(decoded)
                
                # Анализируем качество первого изображения
                quality_analysis = self.image_analyzer.analyze_image_quality(images[0]) if images else {}
                
                # Сохраняем изображения в base64
                pages_data = []
                preview_images = []
                
                for page_num, img in enumerate(images):
                    # Конвертируем в base64
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    img_b64 = base64.b64encode(buffer.getvalue()).decode()
                    pages_data.append(img_b64)
                    
                    # Создаем превью для первых 3 страниц
                    if page_num < 3:
                        # Создаем миниатюру
                        thumbnail = img.copy()
                        thumbnail.thumbnail((200, 300), Image.LANCZOS)
                        thumb_buffer = io.BytesIO()
                        thumbnail.save(thumb_buffer, format='PNG')
                        thumb_b64 = base64.b64encode(thumb_buffer.getvalue()).decode()
                        
                        preview_images.append(
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardImg(
                                        src=f"data:image/png;base64,{thumb_b64}",
                                        top=True,
                                        style={'height': '200px', 'object-fit': 'contain'}
                                    ),
                                    dbc.CardBody([
                                        html.H6(f"Страница {page_num + 1}", className="text-center mb-1"),
                                        html.Small(f"{img.width}×{img.height} px", 
                                                 className="text-muted text-center d-block")
                                    ], className="py-2")
                                ], className="shadow-sm")
                            ], width=4, className="mb-3")
                        )
                
                # Панель превью
                preview_panel = dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-file-pdf me-2"),
                        f"Загружен файл: {filename} ({len(pages_data)} стр.)"
                    ], className="fw-bold"),
                    dbc.CardBody([
                        dbc.Row(preview_images) if preview_images else 
                        html.P("Нет страниц для отображения", className="text-muted text-center")
                    ])
                ], className="shadow-sm")
                
                # Статус панель
                status_panel = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"Файл успешно загружен! Найдено страниц: {len(pages_data)}. ",
                    "Выберите конфигурацию и запустите OCR."
                ], color="success", className="mb-0")
                
                logger.info(f"PDF загружен: {filename}, страниц: {len(pages_data)}")
                return pages_data, preview_panel, False, status_panel, quality_analysis
                
            except Exception as e:
                logger.error(f"Ошибка загрузки PDF: {e}")
                error_panel = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Ошибка загрузки файла: {str(e)}"
                ], color="danger", className="mb-0")
                
                return None, None, True, error_panel, None
        
        @self.app.callback(
            Output('quality-analysis-panel', 'children'),
            [Input('image-quality-store', 'data')]
        )
        def update_quality_analysis(quality_data):
            """Отображение анализа качества изображения"""
            if not quality_data:
                return None
            
            # Создаем карточку с анализом качества
            quality_score = quality_data.get('quality_score', 0)
            suggestions = self.image_analyzer.suggest_improvements(quality_data)
            
            # Определяем цвет в зависимости от качества
            if quality_score >= 0.8:
                color = "success"
                icon = "fas fa-check-circle"
            elif quality_score >= 0.6:
                color = "warning"
                icon = "fas fa-exclamation-triangle"
            else:
                color = "danger"
                icon = "fas fa-times-circle"
            
            return dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-chart-pie me-2"),
                    "Анализ качества изображения"
                ], className="fw-bold"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Alert([
                                html.I(className=f"{icon} me-2"),
                                f"Оценка качества: {quality_score:.1%}"
                            ], color=color, className="mb-3"),
                            
                            # Метрики качества
                            html.H6("Параметры изображения:", className="mb-2"),
                            dbc.ListGroup([
                                dbc.ListGroupItem([
                                    html.Strong("Размер: "),
                                    f"{quality_data.get('width', 0)}×{quality_data.get('height', 0)} пикселей"
                                ]),
                                dbc.ListGroupItem([
                                    html.Strong("Резкость: "),
                                    f"{quality_data.get('sharpness', 0):.1f}"
                                ]),
                                dbc.ListGroupItem([
                                    html.Strong("Контраст: "),
                                    f"{quality_data.get('contrast', 0):.1f}"
                                ]),
                                dbc.ListGroupItem([
                                    html.Strong("Яркость: "),
                                    f"{quality_data.get('brightness', 0):.1f}"
                                ])
                            ], flush=True)
                        ], width=6),
                        
                        dbc.Col([
                            html.H6("Рекомендации по улучшению:", className="mb-2"),
                            html.Div([
                                dbc.Alert([
                                    html.I(className="fas fa-lightbulb me-2"),
                                    suggestion
                                ], color="info", className="py-2 px-3 mb-2")
                                for suggestion in suggestions
                            ] if suggestions else [
                                dbc.Alert([
                                    html.I(className="fas fa-thumbs-up me-2"),
                                    "Качество изображения хорошее! Дополнительная обработка не требуется."
                                ], color="success", className="py-2 px-3")
                            ])
                        ], width=6)
                    ])
                ])
            ], className="shadow-sm mb-4")
        
        @self.app.callback(
            [Output('ocr-results-panel', 'children'),
             Output('ocr-results-store', 'data'),
             Output('processing-status-store', 'data')],
            [Input('run-ocr-btn', 'n_clicks')],
            [State('pdf-pages-store', 'data'),
             State('config-selector', 'value'),
             State('rotation-selector', 'value'),
             State('advanced-options', 'value')]
        )
        def run_ocr_processing(n_clicks, pages_data, config_key, rotation, advanced_options):
            """Запуск OCR обработки с расширенными возможностями"""
            if not n_clicks or not pages_data or not config_key:
                raise PreventUpdate
            
            try:
                # Получаем конфигурацию
                config = get_config(config_key)
                
                # Создаем движок неуверенности
                uncertainty_engine = UncertaintyEngine(config.organization)
                
                # Настройки обработки
                processing_options = {
                    'enhance': 'enhance' in (advanced_options or []),
                    'denoise': 'denoise' in (advanced_options or []),
                    'deskew': 'deskew' in (advanced_options or []),
                    'aggressive': 'aggressive' in (advanced_options or [])
                }
                
                # Обрабатываем каждую страницу
                all_results = []
                result_panels = []
                
                for page_num, page_b64 in enumerate(pages_data):
                    logger.info(f"Обработка страницы {page_num + 1}")
                    
                    # Загружаем изображение
                    img_data = base64.b64decode(page_b64)
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Применяем поворот
                    if rotation:
                        img = self.image_processor.rotate_image(img, rotation)
                    
                    # Применяем дополнительную обработку
                    if processing_options['enhance']:
                        img = self.image_processor.enhance_image_advanced(img)
                    
                    if processing_options['denoise']:
                        img = self.image_processor.denoise_image(img, method='bilateral')
                    
                    if processing_options['deskew']:
                        img = self.image_processor.skew_correction(img)
                    
                    # Изменяем размер
                    img = self.image_processor.resize_image(img)
                    
                    # Извлекаем поля
                    result = self.doc_processor.extract_fields(
                        img, config.__dict__, uncertainty_engine
                    )
                    result['page'] = page_num + 1
                    result['processing_options'] = processing_options
                    all_results.append(result)
                    
                    # Создаем панель результатов для страницы
                    page_panel = self.create_enhanced_page_result_panel(
                        result, page_num + 1, img, config.__dict__
                    )
                    result_panels.append(page_panel)
                
                # Общая панель результатов
                summary_panel = self.create_enhanced_summary_panel(all_results, config)
                
                final_panel = html.Div([
                    summary_panel,
                    html.Hr(className="my-4"),
                    html.Div(result_panels, className="ocr-result")
                ])
                
                logger.info(f"OCR завершен для {len(all_results)} страниц")
                return final_panel, all_results, {'status': 'completed', 'pages': len(all_results)}
                
            except Exception as e:
                logger.error(f"Ошибка OCR: {e}")
                error_panel = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Ошибка OCR обработки: {str(e)}"
                ], color="danger")
                
                return error_panel, None, {'status': 'error', 'message': str(e)}
        
        @self.app.callback(
            Output('analytics-content', 'children'),
            [Input('ocr-results-store', 'data')]
        )
        def update_analytics(ocr_results):
            """Обновление аналитики на основе результатов OCR"""
            if not ocr_results:
                return html.P("Нет данных для анализа", className="text-muted text-center py-5")
            
            # Создаем DataFrame для анализа
            df = pd.DataFrame(ocr_results)
            
            # Статистики
            total_pages = len(df)
            total_uncertainties = sum(len(r.get('uncertainties', [])) for r in ocr_results)
            success_rate = (total_pages - len([r for r in ocr_results if r.get('uncertainties')])) / total_pages * 100
            
            # Создаем графики
            uncertainty_fig = px.bar(
                x=[f"Страница {i+1}" for i in range(total_pages)],
                y=[len(r.get('uncertainties', [])) for r in ocr_results],
                title="Количество неуверенностей по страницам",
                labels={'x': 'Страница', 'y': 'Количество неуверенностей'}
            )
            uncertainty_fig.update_layout(showlegend=False)
            
            return html.Div([
                # Статистические карточки
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H2(f"{total_pages}", className="stat-number text-primary"),
                                html.P("Страниц обработано", className="stat-label")
                            ])
                        ], className="text-center stat-card")
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H2(f"{success_rate:.1f}%", className="stat-number text-success"),
                                html.P("Успешность распознавания", className="stat-label")
                            ])
                        ], className="text-center stat-card")
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H2(f"{total_uncertainties}", className="stat-number text-warning"),
                                html.P("Всего предупреждений", className="stat-label")
                            ])
                        ], className="text-center stat-card")
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H2(f"{total_uncertainties/total_pages:.1f}", className="stat-number text-info"),
                                html.P("Среднее на страницу", className="stat-label")
                            ])
                        ], className="text-center stat-card")
                    ], width=3)
                ], className="stats-grid mb-4"),
                
                # График неуверенностей
                dbc.Card([
                    dbc.CardHeader("График неуверенностей по страницам"),
                    dbc.CardBody([
                        dcc.Graph(figure=uncertainty_fig)
                    ])
                ])
            ])
    
    def create_enhanced_page_result_panel(self, result: Dict, page_num: int, 
                                        img: Image.Image, config: Dict) -> dbc.Card:
        """
        Создание улучшенной панели результатов для страницы
        """
        # Создаем изображение с выделенными областями
        marked_img = self.doc_processor.display_image_with_boxes(
            img, config.get('fields', [])
        )
        
        # Конвертируем в base64
        buffer = io.BytesIO()
        marked_img.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Создаем таблицу результатов
        result_items = []
        uncertainties = result.get('uncertainties', [])
        
        for field_config in config.get('fields', []):
            field_name = field_config['name']
            field_value = result.get(field_name, 'NOT_EXTRACTED')
            
            # Проверяем неуверенность
            is_uncertain = any(u['field'] == field_name for u in uncertainties)
            
            # Обработка серии и номера
            if field_name == 'seriesandnumber':
                series = result.get('series', '')
                number = result.get('number', '')
                field_value = f"{series} {number}" if series and number else 'NOT_EXTRACTED'
            
            # Определяем стиль строки
            if is_uncertain:
                row_class = "table-warning"
                icon = html.I(className="fas fa-exclamation-triangle text-warning me-2")
            elif field_value == 'NOT_EXTRACTED':
                row_class = "table-danger"
                icon = html.I(className="fas fa-times-circle text-danger me-2")
            else:
                row_class = "table-success"
                icon = html.I(className="fas fa-check-circle text-success me-2")
            
            result_items.append(
                html.Tr([
                    html.Td([
                        icon,
                        html.Strong(get_field_description(field_name))
                    ]),
                    html.Td([
                        html.Code(str(field_value), className="bg-light px-2 py-1 rounded"),
                        dbc.Button(
                            html.I(className="fas fa-copy"),
                            id={'type': 'copy-btn', 'index': f"{page_num}_{field_name}"},
                            color="outline-secondary",
                            size="sm",
                            className="ms-2"
                        ) if field_value != 'NOT_EXTRACTED' else ""
                    ])
                ], className=row_class)
            )
        
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-file-alt me-2"),
                f"Страница {page_num}",
                dbc.Badge(
                    f"{len(uncertainties)} предупреждений" if uncertainties else "ОК",
                    color="warning" if uncertainties else "success",
                    className="ms-auto"
                )
            ], className="d-flex align-items-center fw-bold"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H6("Извлеченные данные:", className="mb-3"),
                        dbc.Table([
                            html.Thead([
                                html.Tr([
                                    html.Th("Поле", width="40%"),
                                    html.Th("Значение", width="60%")
                                ])
                            ]),
                            html.Tbody(result_items)
                        ], striped=True, bordered=True, hover=True, size="sm", className="mb-3"),
                        
                        dbc.ButtonGroup([
                            dbc.Button(
                                [html.I(className="fas fa-chart-line me-2"), "Детали"],
                                id={'type': 'show-details-btn', 'index': page_num},
                                color="info",
                                size="sm"
                            ),
                            dbc.Button(
                                [html.I(className="fas fa-download me-2"), "JSON"],
                                id={'type': 'export-json-btn', 'index': page_num},
                                color="success",
                                size="sm"
                            )
                        ])
                    ], width=6),
                    
                    dbc.Col([
                        html.H6("Изображение с разметкой:", className="mb-3"),
                        html.Img(
                            src=f"data:image/png;base64,{img_b64}",
                            style={'width': '100%', 'max-height': '500px', 'object-fit': 'contain'},
                            className="border rounded shadow-sm"
                        )
                    ], width=6)
                ])
            ])
        ], className="result-card mb-4 shadow-sm")
    
    def create_enhanced_summary_panel(self, all_results: List[Dict], config) -> dbc.Card:
        """
        Создание улучшенной сводной панели результатов
        """
        total_pages = len(all_results)
        total_uncertainties = sum(len(r.get('uncertainties', [])) for r in all_results)
        success_rate = (total_pages - len([r for r in all_results if r.get('uncertainties')])) / total_pages * 100
        
        # Создаем DataFrame для экспорта
        export_data = []
        for result in all_results:
            row = {
                'Страница': result.get('page', 1),
                'ФИО': result.get('fullname', ''),
                'Серия': result.get('series', ''),
                'Номер': result.get('number', ''),
                'Рег.номер': result.get('registrationnumber', ''),
                'Дата выдачи': result.get('issuedate', ''),
                'Неуверенности': len(result.get('uncertainties', []))
            }
            export_data.append(row)
        
        df = pd.DataFrame(export_data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Экспорт в CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_b64 = base64.b64encode(csv_buffer.getvalue().encode()).decode()
        
        # Экспорт в JSON
        json_data = json.dumps(all_results, ensure_ascii=False, indent=2, default=str)
        json_b64 = base64.b64encode(json_data.encode()).decode()
        
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-chart-pie me-2"),
                "Сводка результатов"
            ], className="fw-bold"),
            dbc.CardBody([
                dbc.Row([
                    # Статистика
                    dbc.Col([
                        dbc.Alert([
                            html.H4([
                                html.I(className="fas fa-file-alt me-2"),
                                f"Обработано страниц: {total_pages}"
                            ], className="mb-3"),
                            html.P([
                                html.Strong("Конфигурация: "), config.name
                            ], className="mb-2"),
                            html.P([
                                html.Strong("Организация: "), config.organization
                            ], className="mb-2"),
                            html.P([
                                html.Strong("Успешность: "), f"{success_rate:.1f}%"
                            ], className="mb-2"),
                            html.P([
                                html.Strong("Предупреждений: "), 
                                html.Span(f"{total_uncertainties}", 
                                         className="text-warning fw-bold" if total_uncertainties > 0 else "text-success fw-bold")
                            ], className="mb-0")
                        ], color="info")
                    ], width=6),
                    
                    # Экспорт
                    dbc.Col([
                        html.H6([
                            html.I(className="fas fa-download me-2"),
                            "Экспорт результатов:"
                        ], className="mb-3"),
                        
                        dbc.ButtonGroup([
                            html.A(
                                dbc.Button(
                                    [html.I(className="fas fa-file-csv me-2"), "CSV"],
                                    color="success",
                                    size="sm"
                                ),
                                href=f"data:text/csv;charset=utf-8;base64,{csv_b64}",
                                download=f"ocr_results_{timestamp}.csv",
                                className="text-decoration-none"
                            ),
                            html.A(
                                dbc.Button(
                                    [html.I(className="fas fa-file-code me-2"), "JSON"],
                                    color="info",
                                    size="sm"
                                ),
                                href=f"data:application/json;charset=utf-8;base64,{json_b64}",
                                download=f"ocr_results_{timestamp}.json",
                                className="text-decoration-none"
                            ),
                            dbc.Button(
                                [html.I(className="fas fa-print me-2"), "Печать"],
                                id="print-results-btn",
                                color="secondary",
                                size="sm"
                            )
                        ], className="export-buttons mb-3"),
                        
                        # Быстрая статистика
                        dbc.ListGroup([
                            dbc.ListGroupItem([
                                html.I(className="fas fa-clock me-2"),
                                f"Время обработки: {datetime.now().strftime('%H:%M:%S')}"
                            ]),
                            dbc.ListGroupItem([
                                html.I(className="fas fa-memory me-2"),
                                f"Среднее предупреждений: {total_uncertainties/total_pages:.1f}"
                            ])
                        ], flush=True)
                    ], width=6)
                ])
            ])
        ], className="summary-panel mb-4 shadow-sm")
    
    def setup_clientside_callbacks(self):
        """
        Настройка клиентских callbacks для улучшения производительности
        """
        # Автосохранение настроек в localStorage
        clientside_callback(
            """
            function(config_value, rotation_value) {
                if (config_value) localStorage.setItem('ocr_config', config_value);
                if (rotation_value !== null) localStorage.setItem('ocr_rotation', rotation_value);
                return window.dash_clientside.no_update;
            }
            """,
            Output('config-selector', 'style'),
            [Input('config-selector', 'value'),
             Input('rotation-selector', 'value')]
        )
        
        # Копирование в буфер обмена
        clientside_callback(
            """
            function(n_clicks_list) {
                if (!n_clicks_list || n_clicks_list.every(x => !x)) {
                    return window.dash_clientside.no_update;
                }
                
                // Найдем какая кнопка была нажата
                const ctx = window.dash_clientside.callback_context;
                if (!ctx.triggered.length) return window.dash_clientside.no_update;
                
                const button_id = JSON.parse(ctx.triggered[0]['prop_id'].split('.')[0]);
                const field_value = document.querySelector(`tr:has(button[id*="${button_id.index}"]) code`);
                
                if (field_value && navigator.clipboard) {
                    navigator.clipboard.writeText(field_value.textContent);
                    // Показываем уведомление
                    console.log('Скопировано в буфер обмена!');
                }
                
                return window.dash_clientside.no_update;
            }
            """,
            Output('status-panel', 'style'),
            [Input({'type': 'copy-btn', 'index': dash.dependencies.ALL}, 'n_clicks')]
        )
    
    def run_server(self, debug: bool = True, host: str = '127.0.0.1', port: int = 8050):
        """
        Запуск веб-сервера
        """
        logger.info(f"🚀 Запуск OCR Dashboard на http://{host}:{port}")
        logger.info("📄 Поддерживаемые документы:")
        logger.info("   • 1Т - Удостоверения и дипломы")
        logger.info("   • РОСНОУ - Удостоверения и дипломы") 
        logger.info("   • Финуниверситет - Удостоверения (2 варианта)")
        logger.info("🎯 Используйте вкладку 'Разметка полей' для новых типов документов")
        
        self.app.run_server(debug=debug, host=host, port=port)


# Дополнительные утилиты
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
