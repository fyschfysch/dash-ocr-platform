"""
Полнофункциональный Dash Dashboard для OCR платформы
С интерактивной разметкой полей, прогресс-барами и визуальным интерфейсом
Версия: 2.0 (Финальная)
"""

import dash
from dash import dcc, html, Input, Output, State, ALL, MATCH, callback_context, no_update
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from PIL import Image, ImageDraw
import pandas as pd
import numpy as np
import io
import base64
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
import json

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.ocr_engine import DocumentProcessor, OCREngine
from core.image_processor import AdvancedImageProcessor
from core.config import get_config, get_available_configs, UncertaintyEngine, get_field_description, DOCUMENT_CONFIGS

logger = logging.getLogger(__name__)


def create_dash_app(tesseract_cmd: Optional[str] = None):
    """
    Создание Dash приложения с полным функционалом
    
    Args:
        tesseract_cmd: Путь к Tesseract
        
    Returns:
        Dash приложение
    """
    doc_processor = DocumentProcessor(tesseract_cmd)
    image_processor = AdvancedImageProcessor()
    
    # Dash автоматически подключит все файлы из assets/
    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            dbc.icons.FONT_AWESOME
        ],
        title="OCR Платформа",
        suppress_callback_exceptions=True
    )
    
    app.layout = create_main_layout()
    setup_callbacks(app, doc_processor, image_processor)
    
    logger.info("Dash приложение инициализировано с полным функционалом")
    
    return app


def create_main_layout() -> html.Div:
    """Создание главного layout с четырьмя режимами работы"""
    return dbc.Container([
        # Заголовок
        dbc.Alert([
            html.H1([
                html.I(className="fas fa-brain me-3"),
                "OCR Платформа для документов об образовании"
            ], className="mb-2"),
            html.P("Интерактивное распознавание с возможностью разметки и редактирования", className="mb-0")
        ], color="primary", className="mb-4 main-header"),
        
        # Вкладки режимов работы
        dbc.Tabs([
            # Режим 1: Быстрое распознавание
            dbc.Tab(
                label="🚀 Быстрое распознавание",
                tab_id="quick-ocr",
                children=create_quick_ocr_tab()
            ),
            
            # Режим 2: Интерактивная разметка
            dbc.Tab(
                label="🎯 Интерактивная разметка",
                tab_id="interactive-markup",
                children=create_interactive_markup_tab()
            ),
            
            # Режим 3: Пакетная обработка
            dbc.Tab(
                label="📦 Пакетная обработка",
                tab_id="batch-processing",
                children=create_batch_processing_tab()
            ),
            
            # Режим 4: Создание конфигураций
            dbc.Tab(
                label="⚙️ Создание конфигурации",
                tab_id="config-creator",
                children=create_config_creator_tab()
            )
        ], id="main-tabs", active_tab="quick-ocr", className="mb-4"),
        
        # Глобальные хранилища данных
        dcc.Store(id='global-pdf-store'),
        dcc.Store(id='global-config-store'),
        dcc.Store(id='global-results-store'),
        dcc.Store(id='markup-boxes-store', data={}),
        dcc.Store(id='current-image-store'),
        dcc.Store(id='processing-status-store', data={'status': 'idle', 'progress': 0}),
        
        # Interval для анимации прогресса
        dcc.Interval(id='progress-interval', interval=200, n_intervals=0, disabled=True),
        
    ], fluid=True, className="py-4")


def create_quick_ocr_tab() -> html.Div:
    """Режим быстрого распознавания"""
    return html.Div([
        dbc.Row([
            # Левая панель - загрузка и настройки
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-file-upload me-2"),
                        "Шаг 1: Загрузите документ"
                    ], className="fw-bold"),
                    dbc.CardBody([
                        dcc.Upload(
                            id='quick-upload',
                            children=dbc.Alert([
                                html.I(className="fas fa-cloud-upload-alt fa-3x mb-3 text-primary"),
                                html.Br(),
                                html.H5("Перетащите PDF или изображение"),
                                html.Small("Поддерживается: PDF, PNG, JPG (до 50MB)", className="text-muted")
                            ], color="light", className="text-center py-4 upload-area"),
                            style={
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '10px',
                                'cursor': 'pointer'
                            },
                            multiple=False
                        ),
                        html.Div(id="quick-upload-status", className="mt-2")
                    ])
                ], className="mb-3 result-card"),
                
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-cog me-2"),
                        "Шаг 2: Выберите тип документа"
                    ], className="fw-bold"),
                    dbc.CardBody([
                        dbc.Label("Тип документа:"),
                        dcc.Dropdown(
                            id='quick-config-select',
                            options=get_config_options(),
                            placeholder="Выберите тип..."
                        ),
                        html.Hr(),
                        dbc.Label("Поворот изображения:"),
                        dcc.Dropdown(
                            id='quick-rotation',
                            options=[
                                {'label': '0° (без поворота)', 'value': 0},
                                {'label': '90° по часовой ↻', 'value': 90},
                                {'label': '180° ↻', 'value': 180},
                                {'label': '270° против часовой ↺', 'value': 270}
                            ],
                            value=0
                        ),
                        html.Hr(),
                        dbc.Checklist(
                            options=[
                                {"label": " Улучшенная предобработка", "value": 1},
                            ],
                            value=[1],
                            id="quick-enhance-check",
                            switch=True,
                        )
                    ])
                ], className="mb-3 result-card"),
                
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-play me-2"),
                        "Шаг 3: Запустите распознавание"
                    ], className="fw-bold"),
                    dbc.CardBody([
                        dbc.Button(
                            [html.I(className="fas fa-rocket me-2"), "Распознать документ"],
                            id="quick-run-btn",
                            color="success",
                            size="lg",
                            className="w-100 mb-3",
                            disabled=True
                        ),
                        html.Div(id="quick-progress-panel")
                    ])
                ], className="result-card")
            ], width=4),
            
            # Правая панель - результаты
            dbc.Col([
                html.Div(id="quick-preview-panel"),
                html.Div(id="quick-results-panel", className="ocr-result")
            ], width=8)
        ])
    ])


def create_interactive_markup_tab() -> html.Div:
    """Режим интерактивной разметки с Plotly"""
    return html.Div([
        dbc.Row([
            # Левая панель - управление
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-file-pdf me-2"),
                        "Загрузка документа"
                    ]),
                    dbc.CardBody([
                        dcc.Upload(
                            id='markup-upload',
                            children=dbc.Alert([
                                html.I(className="fas fa-file-pdf fa-2x mb-2 text-primary"),
                                html.Br(),
                                html.Strong("Загрузить образец"),
                                html.Br(),
                                html.Small("PDF, PNG, JPG")
                            ], color="light", className="text-center py-3 upload-area"),
                            style={
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '8px',
                                'cursor': 'pointer'
                            }
                        ),
                        html.Div(id="markup-upload-info", className="mt-2")
                    ])
                ], className="mb-3"),
                
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-list me-2"),
                        "Конфигурация"
                    ]),
                    dbc.CardBody([
                        dbc.Label("Базовая конфигурация:"),
                        dcc.Dropdown(
                            id='markup-base-config',
                            options=[{'label': '🆕 Новая (пустая)', 'value': 'empty'}] + get_config_options(),
                            value='empty'
                        ),
                        html.Hr(),
                        dbc.Label("Режим работы:"),
                        dbc.RadioItems(
                            id='markup-mode',
                            options=[
                                {'label': '👁️ Просмотр полей', 'value': 'view'},
                                {'label': '✏️ Рисование областей', 'value': 'draw'},
                                {'label': '📝 Редактирование координат', 'value': 'edit'}
                            ],
                            value='view',
                            inline=False
                        ),
                        html.Small("В режиме рисования кликните и перетащите мышью для создания области", 
                                 className="text-muted d-block mt-2")
                    ])
                ], className="mb-3"),
                
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-th-list me-2"),
                        "Поля документа"
                    ]),
                    dbc.CardBody([
                        html.Div(id="markup-fields-panel"),
                        dbc.Button(
                            [html.I(className="fas fa-plus me-2"), "Добавить поле"],
                            id="add-field-btn",
                            color="secondary",
                            size="sm",
                            outline=True,
                            className="w-100 mt-2"
                        )
                    ])
                ], className="mb-3"),
                
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-tools me-2"),
                        "Действия"
                    ]),
                    dbc.CardBody([
                        dbc.Button(
                            [html.I(className="fas fa-play me-2"), "Распознать с текущей разметкой"],
                            id="markup-run-ocr",
                            color="success",
                            className="w-100 mb-2"
                        ),
                        dbc.Button(
                            [html.I(className="fas fa-save me-2"), "Сохранить конфигурацию"],
                            id="markup-save-config",
                            color="primary",
                            className="w-100 mb-2"
                        ),
                        dbc.Button(
                            [html.I(className="fas fa-download me-2"), "Экспорт в JSON"],
                            id="markup-export-json",
                            color="info",
                            className="w-100"
                        )
                    ])
                ])
            ], width=3),
            
            # Правая панель - интерактивное изображение
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Span([
                            html.I(className="fas fa-crosshairs me-2"),
                            "Интерактивная разметка"
                        ], className="me-3"),
                        dbc.Badge(id="markup-status-badge", color="secondary", children="Готов к работе")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(
                            id='markup-interactive-image',
                            config={
                                'displayModeBar': True,
                                'displaylogo': False,
                                'modeBarButtonsToAdd': ['drawrect', 'eraseshape'],
                                'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'zoom2d', 'pan2d']
                            },
                            style={'height': '70vh'}
                        ),
                        html.Div(id="markup-coordinates-display", className="mt-3")
                    ])
                ], className="mb-3 result-card"),
                
                html.Div(id="markup-ocr-results")
            ], width=9)
        ])
    ])


def create_batch_processing_tab() -> html.Div:
    """Режим пакетной обработки"""
    return html.Div([
        dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            "Загрузите несколько PDF файлов для одновременной обработки. Все файлы должны быть одного типа."
        ], color="info", className="mb-3"),
        
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-folder-open me-2"),
                "Пакетная загрузка файлов"
            ], className="fw-bold"),
            dbc.CardBody([
                dcc.Upload(
                    id='batch-upload',
                    children=dbc.Alert([
                        html.I(className="fas fa-folder-open fa-3x mb-3 text-primary"),
                        html.Br(),
                        html.H5("Перетащите несколько PDF файлов"),
                        html.Small("Или нажмите для выбора нескольких файлов")
                    ], color="light", className="text-center py-5 upload-area"),
                    style={
                        'borderWidth': '3px',
                        'borderStyle': 'dashed',
                        'borderRadius': '10px',
                        'cursor': 'pointer'
                    },
                    multiple=True
                ),
                
                html.Hr(),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Тип всех документов:"),
                        dcc.Dropdown(
                            id='batch-config-select',
                            options=get_config_options(),
                            placeholder="Выберите единый тип"
                        )
                    ], width=8),
                    dbc.Col([
                        html.Br(),
                        dbc.Button(
                            [html.I(className="fas fa-cogs me-2"), "Обработать все"],
                            id="batch-process-btn",
                            color="primary",
                            size="lg",
                            className="w-100",
                            disabled=True
                        )
                    ], width=4)
                ])
            ])
        ], className="mb-3 result-card"),
        
        html.Div(id="batch-progress-panel", className="mb-3"),
        html.Div(id="batch-results-panel")
    ])


def create_config_creator_tab() -> html.Div:
    """Режим создания новых конфигураций"""
    return html.Div([
        dbc.Alert([
            html.H5([html.I(className="fas fa-magic me-2"), "Мастер создания конфигурации"]),
            html.P("Создайте конфигурацию для нового типа документа пошагово", className="mb-0")
        ], color="success", className="mb-3"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Шаг 1: Информация о конфигурации"),
                    dbc.CardBody([
                        dbc.Label("Название конфигурации:"),
                        dbc.Input(
                            id="config-name-input", 
                            placeholder="Например: МГУ - Диплом 2024",
                            className="mb-3"
                        ),
                        dbc.Label("Код организации (на английском):"),
                        dbc.Input(
                            id="config-org-input", 
                            placeholder="Например: MSU",
                            className="mb-3"
                        ),
                        dbc.Label("Тип документа:"),
                        dcc.Dropdown(
                            id="config-type-select",
                            options=[
                                {'label': 'Диплом о переподготовке', 'value': 'diploma'},
                                {'label': 'Удостоверение о повышении квалификации', 'value': 'certificate'},
                                {'label': 'Свидетельство', 'value': 'attestation'},
                                {'label': 'Другое', 'value': 'other'}
                            ],
                            placeholder="Выберите тип"
                        )
                    ])
                ])
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Шаг 2: Загрузка образца"),
                    dbc.CardBody([
                        dcc.Upload(
                            id='config-sample-upload',
                            children=html.Div([
                                html.I(className="fas fa-image fa-2x mb-2 text-info"),
                                html.Br(),
                                "Загрузить образец документа"
                            ], className="text-center py-4 upload-area"),
                            style={
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '8px',
                                'padding': '20px',
                                'cursor': 'pointer'
                            }
                        ),
                        html.Div(id="config-sample-preview", className="mt-3")
                    ])
                ])
            ], width=6)
        ], className="mb-3"),
        
        dbc.Card([
            dbc.CardHeader("Шаг 3: Разметка полей"),
            dbc.CardBody([
                dbc.Alert([
                    html.I(className="fas fa-arrow-right me-2"),
                    "Перейдите на вкладку 'Интерактивная разметка' для создания разметки полей"
                ], color="info"),
                dbc.Button(
                    [html.I(className="fas fa-external-link-alt me-2"), "Открыть инструмент разметки →"],
                    id="goto-markup-btn",
                    color="info",
                    outline=True
                )
            ])
        ], className="mb-3"),
        
        dbc.Card([
            dbc.CardHeader("Шаг 4: Генерация кода конфигурации"),
            dbc.CardBody([
                dbc.Button(
                    [html.I(className="fas fa-code me-2"), "Сгенерировать Python код"],
                    id="generate-config-code-btn",
                    color="success",
                    className="mb-3"
                ),
                html.Pre(
                    id="generated-config-code", 
                    style={
                        'backgroundColor': '#f8f9fa', 
                        'padding': '15px',
                        'borderRadius': '5px',
                        'maxHeight': '400px',
                        'overflow': 'auto'
                    }
                ),
                dbc.Button(
                    [html.I(className="fas fa-copy me-2"), "Копировать код"],
                    id="copy-config-code-btn",
                    color="primary",
                    size="sm",
                    className="mt-2"
                )
            ])
        ])
    ])


def get_config_options() -> List[Dict]:
    """Получение опций конфигураций"""
    configs = get_available_configs()
    return [{'label': f"{c['organization']} - {c['name']}", 'value': c['id']} for c in configs]


def create_interactive_plotly_image(img: Image.Image, boxes: Dict = None, 
                                   mode: str = 'view') -> go.Figure:
    """
    Создание интерактивного изображения с Plotly
    
    Args:
        img: PIL изображение
        boxes: Словарь с координатами полей {field_name: (x1, y1, x2, y2)}
        mode: Режим ('view', 'draw', 'edit')
    """
    img_array = np.array(img)
    
    fig = go.Figure()
    
    # Добавляем изображение
    fig.add_trace(go.Image(z=img_array))
    
    # Добавляем прямоугольники полей
    if boxes:
        colors = ['red', 'green', 'blue', 'orange', 'purple', 'cyan', 'magenta', 'yellow']
        for i, (field_name, box) in enumerate(boxes.items()):
            if box and len(box) == 4:
                x0, y0, x1, y1 = box
                color = colors[i % len(colors)]
                
                # Рисуем прямоугольник
                fig.add_shape(
                    type="rect",
                    x0=x0, y0=y0, x1=x1, y1=y1,
                    line=dict(color=color, width=3),
                    name=field_name
                )
                
                # Добавляем подпись
                fig.add_annotation(
                    x=x0, y=y0,
                    text=get_field_description(field_name),
                    showarrow=False,
                    bgcolor=color,
                    font=dict(color='white', size=12),
                    yshift=-10
                )
    
    # Настройки layout
    fig.update_layout(
        dragmode='drawrect' if mode == 'draw' else 'pan',
        newshape=dict(line=dict(color='red', width=3)),
        height=800,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, scaleanchor="x"),
        plot_bgcolor='white'
    )
    
    return fig


def setup_callbacks(app, doc_processor, image_processor):
    """Настройка всех callbacks"""
    
    # Callback: Быстрая загрузка PDF с анимацией загрузки
    @app.callback(
        [Output('quick-preview-panel', 'children'),
         Output('global-pdf-store', 'data'),
         Output('quick-run-btn', 'disabled'),
         Output('quick-upload-status', 'children')],
        [Input('quick-upload', 'contents')],
        [State('quick-upload', 'filename')]
    )
    def quick_load_pdf(contents, filename):
        if not contents:
            return no_update, no_update, True, ""
        
        try:
            # Показываем статус загрузки
            loading_status = dbc.Spinner(
                html.Small("Загрузка и обработка..."), 
                color="primary",
                size="sm"
            )
            
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            images = image_processor.convert_pdf_from_bytes(decoded)
            
            if not images:
                error = dbc.Alert("❌ Ошибка загрузки файла", color="danger", className="small")
                return None, None, True, error
            
            # Сохраняем изображения
            images_b64 = []
            for img in images:
                img_resized = image_processor.resize_image(img)
                buffer = io.BytesIO()
                img_resized.save(buffer, format='PNG')
                img_b64 = base64.b64encode(buffer.getvalue()).decode()
                images_b64.append(img_b64)
            
            # Превью первой страницы
            preview = dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-file-pdf me-2"),
                    f"{filename}",
                    dbc.Badge(f"{len(images)} стр.", color="info", className="ms-2")
                ]),
                dbc.CardBody([
                    html.Img(
                        src=f"data:image/png;base64,{images_b64[0]}",
                        style={'width': '100%', 'maxHeight': '600px', 'objectFit': 'contain'},
                        className="border rounded"
                    )
                ])
            ], className="result-card")
            
            success_status = dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"✓ Загружено: {len(images)} стр."
            ], color="success", className="small")
            
            return preview, images_b64, False, success_status
            
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            error = dbc.Alert(f"❌ Ошибка: {str(e)}", color="danger", className="small")
            return None, None, True, error
    
    # Callback: Отображение полей при выборе конфигурации
    @app.callback(
        Output('quick-preview-panel', 'children', allow_duplicate=True),
        [Input('quick-config-select', 'value')],
        [State('global-pdf-store', 'data'),
         State('quick-upload', 'filename')],
        prevent_initial_call=True
    )
    def show_fields_preview(config_id, pdf_data, filename):
        if not config_id or not pdf_data:
            raise PreventUpdate
        
        try:
            config = get_config(config_id)
            
            img_data = base64.b64decode(pdf_data[0])
            img = Image.open(io.BytesIO(img_data))
            
            img_with_boxes = doc_processor.display_image_with_boxes(img, config.fields)
            
            buffer = io.BytesIO()
            img_with_boxes.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            preview = dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-file-pdf me-2"),
                    f"{filename}",
                    dbc.Badge(config.name, color="info", className="ms-2")
                ]),
                dbc.CardBody([
                    html.Img(
                        src=f"data:image/png;base64,{img_b64}",
                        style={'width': '100%', 'maxHeight': '600px', 'objectFit': 'contain'},
                        className="border rounded"
                    ),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        f"Настроенные поля: {len(config.fields)}"
                    ], className="text-muted d-block mt-2")
                ])
            ], className="result-card")
            
            return preview
            
        except Exception as e:
            logger.error(f"Ошибка отображения полей: {e}")
            raise PreventUpdate
    
    # Callback: Быстрое распознавание с прогресс-баром
    @app.callback(
        [Output('quick-results-panel', 'children'),
         Output('quick-progress-panel', 'children'),
         Output('global-results-store', 'data')],
        [Input('quick-run-btn', 'n_clicks')],
        [State('global-pdf-store', 'data'),
         State('quick-config-select', 'value'),
         State('quick-rotation', 'value'),
         State('quick-enhance-check', 'value')]
    )
    def quick_run_ocr(n_clicks, pdf_data, config_id, rotation, enhance):
        if not n_clicks or not pdf_data or not config_id:
            raise PreventUpdate
        
        try:
            # Показываем прогресс
            progress = dbc.Progress(
                value=10,
                label="Инициализация...",
                striped=True,
                animated=True,
                color="success",
                className="mb-2",
                style={'height': '30px'}
            )
            
            config = get_config(config_id)
            uncertainty_engine = UncertaintyEngine(config.organization)
            
            all_results = []
            total_pages = len(pdf_data)
            
            for page_num, img_b64 in enumerate(pdf_data):
                img_data = base64.b64decode(img_b64)
                img = Image.open(io.BytesIO(img_data))
                
                if rotation:
                    img = image_processor.rotate_image(img, rotation)
                
                if enhance and 1 in enhance:
                    img = image_processor.enhance_image_advanced(img)
                
                result = doc_processor.extract_fields(img, config, uncertainty_engine)
                result['page'] = page_num + 1
                
                # Миниатюры полей
                result['field_thumbnails'] = {}
                for field_config in config.fields:
                    field_name = field_config['name']
                    box = field_config.get('box')
                    
                    if box:
                        thumbnail = doc_processor.crop_field_thumbnail(img, box)
                        thumb_buffer = io.BytesIO()
                        thumbnail.save(thumb_buffer, format='PNG')
                        thumb_b64 = base64.b64encode(thumb_buffer.getvalue()).decode()
                        result['field_thumbnails'][field_name] = thumb_b64
                
                all_results.append(result)
            
            # Создаем интерфейс результатов
            results_ui = create_results_interface(all_results, config)
            
            success_status = dbc.Alert([
                html.I(className="fas fa-check-circle me-2"),
                f"✓ Обработано страниц: {total_pages}"
            ], color="success")
            
            return results_ui, success_status, all_results
            
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}", exc_info=True)
            error = dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"Ошибка распознавания: {str(e)}"
            ], color="danger")
            return error, error, None
    
    # Callback: Интерактивная разметка - загрузка изображения
    @app.callback(
        [Output('markup-interactive-image', 'figure'),
         Output('current-image-store', 'data'),
         Output('markup-upload-info', 'children')],
        [Input('markup-upload', 'contents'),
         Input('markup-base-config', 'value'),
         Input('markup-mode', 'value')],
        [State('markup-upload', 'filename')]
    )
    def update_interactive_image(contents, base_config, mode, filename):
        if not contents:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                annotations=[{
                    'text': 'Загрузите изображение для начала работы',
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 20, 'color': 'gray'}
                }]
            )
            return empty_fig, None, ""
        
        try:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            images = image_processor.convert_pdf_from_bytes(decoded)
            img = images[0]
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Загружаем boxes из конфигурации если выбрана
            boxes = {}
            if base_config and base_config != 'empty':
                config = get_config(base_config)
                for field in config.fields:
                    boxes[field['name']] = field.get('box')
            
            # Создаем интерактивную фигуру
            fig = create_interactive_plotly_image(img, boxes, mode)
            
            info = dbc.Alert([
                html.I(className="fas fa-check me-2"),
                f"Загружено: {filename} ({img.size[0]}×{img.size[1]}px)"
            ], color="success", className="small")
            
            return fig, img_b64, info
            
        except Exception as e:
            logger.error(f"Ошибка загрузки для разметки: {e}")
            empty_fig = go.Figure()
            error_info = dbc.Alert(f"Ошибка: {str(e)}", color="danger", className="small")
            return empty_fig, None, error_info
    
    # Callback: Отображение координат нарисованных областей
    @app.callback(
        [Output('markup-coordinates-display', 'children'),
         Output('markup-status-badge', 'children'),
         Output('markup-status-badge', 'color')],
        [Input('markup-interactive-image', 'relayoutData')]
    )
    def display_drawn_coordinates(relayout_data):
        if not relayout_data:
            return "", "Готов к работе", "secondary"
        
        # Проверяем наличие нарисованных фигур
        if 'shapes' in relayout_data:
            shapes = relayout_data['shapes']
            if shapes:
                coords_info = []
                for i, shape in enumerate(shapes):
                    if shape['type'] == 'rect':
                        x0 = int(shape['x0'])
                        y0 = int(shape['y0'])
                        x1 = int(shape['x1'])
                        y1 = int(shape['y1'])
                        coords_info.append(
                            html.Li(f"Область {i+1}: ({x0}, {y0}, {x1}, {y1})")
                        )
                
                if coords_info:
                    alert = dbc.Alert([
                        html.H6([
                            html.I(className="fas fa-vector-square me-2"),
                            "Нарисованные области:"
                        ]),
                        html.Ul(coords_info, className="mb-0")
                    ], color="info")
                    
                    return alert, f"{len(shapes)} областей", "success"
        
        return "", "Рисуйте области", "warning"
    
    # Callback: Принятие исправлений
    @app.callback(
        Output({'type': 'field-status', 'page': MATCH, 'field': MATCH}, 'children'),
        [Input({'type': 'accept-btn', 'page': MATCH, 'field': MATCH}, 'n_clicks')],
        prevent_initial_call=True
    )
    def accept_field_correction(n_clicks):
        if not n_clicks:
            raise PreventUpdate
        
        return html.Span([
            html.I(className="fas fa-check-circle text-success me-1"),
            "✓"
        ])


def create_results_interface(results: List[Dict], config) -> html.Div:
    """Создание интерфейса результатов"""
    components = [
        create_summary_panel(results, config),
        html.Hr()
    ]
    
    for page_result in results:
        page_table = create_editable_page_table(page_result, config)
        components.append(page_table)
    
    return html.Div(components)


def create_editable_page_table(page_result: Dict, config) -> dbc.Card:
    """Создание редактируемой таблицы результатов"""
    page_num = page_result['page']
    uncertainties = page_result.get('uncertainties', [])
    uncertain_fields = {u['field'] for u in uncertainties}
    field_thumbnails = page_result.get('field_thumbnails', {})
    
    table_rows = []
    
    for field_config in config.fields:
        field_name = field_config['name']
        field_display = get_field_description(field_name)
        
        if field_name == 'series_and_number':
            value = f"{page_result.get('series', '')} {page_result.get('number', '')}".strip()
        else:
            value = page_result.get(field_name, '')
        
        thumb_b64 = field_thumbnails.get(field_name, '')
        is_uncertain = field_name in uncertain_fields
        
        row_class = "table-warning" if is_uncertain else ""
        
        row = html.Tr([
            html.Td([
                html.I(className="fas fa-exclamation-triangle text-warning me-1") if is_uncertain else "",
                field_display
            ], style={'width': '20%'}),
            html.Td([
                html.Img(
                    src=f"data:image/png;base64,{thumb_b64}",
                    style={'maxWidth': '120px', 'maxHeight': '80px', 'objectFit': 'contain'},
                    className="border"
                ) if thumb_b64 else "—"
            ], style={'width': '15%', 'textAlign': 'center'}),
            html.Td([
                dcc.Input(
                    id={'type': 'field-input', 'page': page_num, 'field': field_name},
                    value=str(value),
                    style={
                        'width': '100%', 
                        'backgroundColor': '#fff3cd' if is_uncertain else '#fff',
                        'padding': '8px'
                    },
                    className="form-control"
                )
            ], style={'width': '45%'}),
            html.Td([
                dbc.Button(
                    "✓",
                    id={'type': 'accept-btn', 'page': page_num, 'field': field_name},
                    color="success",
                    size="sm",
                    className="me-2"
                ),
                html.Span(
                    id={'type': 'field-status', 'page': page_num, 'field': field_name}
                )
            ], style={'width': '20%'})
        ], className=row_class)
        
        table_rows.append(row)
    
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-file-alt me-2"),
            f"Страница {page_num}"
        ], className="fw-bold"),
        dbc.CardBody([
            dbc.Table([
                html.Thead([html.Tr([
                    html.Th("Поле"),
                    html.Th("Превью"),
                    html.Th("Значение"),
                    html.Th("Действие")
                ])]),
                html.Tbody(table_rows)
            ], bordered=True, hover=True, responsive=True)
        ])
    ], className="mb-4 result-card")


def create_summary_panel(results: List[Dict], config) -> dbc.Card:
    """Создание сводной панели с экспортом"""
    total_pages = len(results)
    total_uncertainties = sum(len(r.get('uncertainties', [])) for r in results)
    
    export_data = []
    for result in results:
        export_data.append({
            'Страница': result['page'],
            'ФИО': result.get('full_name', ''),
            'Серия': result.get('series', ''),
            'Номер': result.get('number', ''),
            'Рег.номер': result.get('registration_number', ''),
            'Дата': result.get('issue_date', '')
        })
    
    df = pd.DataFrame(export_data)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    csv_b64 = base64.b64encode(csv_buffer.getvalue().encode()).decode()
    
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    json_b64 = base64.b64encode(json_str.encode()).decode()
    
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-chart-bar me-2"),
            "Сводка результатов"
        ], className="fw-bold"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H4([
                        html.I(className="fas fa-file-alt me-2"),
                        f"{total_pages}"
                    ]),
                    html.P("Обработано страниц", className="text-muted"),
                    html.Hr(),
                    html.P(f"📋 Конфигурация: {config.name}", className="small"),
                    html.P([
                        html.I(className="fas fa-exclamation-triangle text-warning me-1") if total_uncertainties > 0 else html.I(className="fas fa-check-circle text-success me-1"),
                        f"{total_uncertainties} полей требуют проверки" if total_uncertainties > 0 else "Все поля распознаны уверенно"
                    ], className="small")
                ], width=6),
                dbc.Col([
                    html.H6("Экспорт результатов:", className="mb-3"),
                    html.A(
                        dbc.Button([
                            html.I(className="fas fa-file-csv me-2"), 
                            "Скачать CSV"
                        ], 
                        color="success", 
                        className="w-100 mb-2 export-btn"),
                        href=f"data:text/csv;charset=utf-8;base64,{csv_b64}",
                        download=f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    ),
                    html.A(
                        dbc.Button([
                            html.I(className="fas fa-file-code me-2"), 
                            "Скачать JSON"
                        ], 
                        color="info", 
                        className="w-100 export-btn"),
                        href=f"data:application/json;base64,{json_b64}",
                        download=f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    )
                ], width=6)
            ])
        ])
    ], className="mb-4 result-card")


if __name__ == '__main__':
    app = create_dash_app()
    app.run(debug=True, port=8050)
