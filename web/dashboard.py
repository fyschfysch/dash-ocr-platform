"""
Dash Dashboard для OCR платформы
Версия: 5.0 (Реализация применения изменений, JSON редактор, улучшенный UX)
"""


import dash
from dash import dcc, html, Input, Output, State, ALL, MATCH, callback_context, no_update
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go


from PIL import Image
import pandas as pd
import numpy as np
import io
import base64
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import json


import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


from core.ocr_engine import DocumentProcessor
from core.image_processor import AdvancedImageProcessor
from core.config import get_config, get_available_configs, UncertaintyEngine, get_field_description


logger = logging.getLogger(__name__)



def create_dash_app(tesseract_cmd: Optional[str] = None):
    """Создание Dash приложения"""
    doc_processor = DocumentProcessor(tesseract_cmd)
    image_processor = AdvancedImageProcessor()
    
    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            dbc.icons.FONT_AWESOME
        ],
        title="Document OCR Platform",
        suppress_callback_exceptions=True
    )
    
    app.layout = create_main_layout()
    setup_callbacks(app, doc_processor, image_processor)
    
    logger.info("Dash приложение инициализировано")
    
    return app



def create_main_layout() -> html.Div:
    """Создание главного layout"""
    return dbc.Container([
        dbc.Alert([
            html.H4("Document OCR Platform", className="mb-1"),
            html.Small([
                "by ",
                html.A("z_loy", href="https://t.me/z_loy", target="_blank", className="text-white")
            ])
        ], color="primary", className="mb-3"),
        
        dbc.Tabs([
            dbc.Tab(
                label="🚀 Быстрое распознавание",
                tab_id="quick-ocr",
                children=create_quick_ocr_tab()
            ),
            dbc.Tab(
                label="🎯 Интерактивная разметка",
                tab_id="interactive-markup",
                children=create_interactive_markup_tab()
            ),
            dbc.Tab(
                label="📦 Пакетная обработка",
                tab_id="batch-processing",
                children=create_batch_processing_tab()
            )
        ], id="main-tabs", active_tab="quick-ocr", className="mb-4"),
        
        dcc.Store(id='global-pdf-store'),
        dcc.Store(id='global-results-store'),
        dcc.Store(id='rotation-angle-store', data=0),
        dcc.Store(id='current-image-store'),
        dcc.Store(id='json-editor-store'),
        
    ], fluid=True, className="py-4")



def create_quick_ocr_tab() -> html.Div:
    """Режим быстрого распознавания - КОМПАКТНАЯ ЛЕВАЯ ПАНЕЛЬ"""
    return html.Div([
        dbc.Row([
            dbc.Col([
                # Компактная карточка загрузки
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-file-upload me-2"),
                        "Загрузка"
                    ], className="fw-bold compact-header"),
                    dbc.CardBody([
                        dcc.Upload(
                            id='quick-upload',
                            children=dbc.Alert([
                                html.I(className="fas fa-cloud-upload-alt fa-2x mb-2 text-primary"),
                                html.Br(),
                                html.Small("PDF, PNG, JPG", className="text-muted")
                            ], color="light", className="text-center py-2 upload-area"),
                            style={
                                'borderWidth': '2px',
                                'borderStyle': 'dashed',
                                'borderRadius': '8px',
                                'cursor': 'pointer'
                            },
                            multiple=False
                        ),
                        html.Div(id="quick-upload-status", className="mt-2")
                    ], className="compact-body")
                ], className="mb-2 result-card"),
                
                # Компактная карточка настроек
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-cog me-2"),
                        "Настройки"
                    ], className="fw-bold compact-header"),
                    dbc.CardBody([
                        dbc.Label("Тип документа:", className="small mb-1"),
                        dcc.Dropdown(
                            id='quick-config-select',
                            options=get_config_options_grouped(),
                            placeholder="Выберите...",
                            className="compact-dropdown",
                            optionHeight=50
                        ),
                        html.Hr(className="my-2"),
                        dbc.Label("Поворот:", className="small mb-1"),
                        dbc.Button(
                            [html.I(className="fas fa-redo me-2"), "90° →"],
                            id='quick-rotation-btn',
                            color="secondary",
                            outline=True,
                            size="sm",
                            className="w-100"
                        ),
                        html.Small(id="rotation-status", className="text-muted d-block mt-1", children="Угол: 0°", style={'fontSize': '0.75rem'}),
                        html.Hr(className="my-2"),
                        dbc.Checklist(
                            options=[{"label": " Улучшение", "value": 1}],
                            value=[1],
                            id="quick-enhance-check",
                            switch=True,
                            className="compact-switch"
                        )
                    ], className="compact-body")
                ], className="mb-2 result-card"),
                
                # Компактная карточка запуска
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-play me-2"),
                        "Запуск"
                    ], className="fw-bold compact-header"),
                    dbc.CardBody([
                        dbc.Button(
                            [html.I(className="fas fa-rocket me-2"), "Распознать"],
                            id="quick-run-btn",
                            color="success",
                            size="lg",
                            className="w-100",
                            disabled=True
                        ),
                        html.Div(id="quick-progress-panel", className="mt-2")
                    ], className="compact-body")
                ], className="result-card")
            ], width=3),
            
            dbc.Col([
                html.Div(id="quick-preview-panel"),
                html.Div(id="quick-results-panel", className="ocr-result")
            ], width=9)
        ])
    ])



def create_interactive_markup_tab() -> html.Div:
    """Режим интерактивной разметки"""
    return html.Div([
        dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            "Загрузите образец документа и используйте инструменты Plotly для рисования областей полей"
        ], color="info", className="mb-3"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Загрузка образца", className="compact-header"),
                    dbc.CardBody([
                        dcc.Upload(
                            id='markup-upload',
                            children=dbc.Alert([
                                html.I(className="fas fa-file-pdf fa-2x mb-2"),
                                html.Br(),
                                html.Strong("Загрузить PDF"),
                            ], color="light", className="text-center py-2 upload-area"),
                            style={'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '8px', 'cursor': 'pointer'}
                        ),
                        html.Div(id="markup-upload-info", className="mt-2")
                    ], className="compact-body")
                ], className="mb-2"),
                
                dbc.Card([
                    dbc.CardHeader("Базовая конфигурация", className="compact-header"),
                    dbc.CardBody([
                        dcc.Dropdown(
                            id='markup-base-config',
                            options=[{'label': '🆕 Новая', 'value': 'empty'}] + get_config_options_grouped(),
                            value='empty',
                            className="compact-dropdown"
                        )
                    ], className="compact-body")
                ], className="mb-2"),
                
                dbc.Card([
                    dbc.CardHeader("Действия", className="compact-header"),
                    dbc.CardBody([
                        dbc.Button(
                            [html.I(className="fas fa-play me-2"), "Распознать"],
                            id="markup-run-ocr",
                            color="success",
                            size="sm",
                            className="w-100 mb-2"
                        ),
                        dbc.Button(
                            [html.I(className="fas fa-download me-2"), "Экспорт"],
                            id="markup-export-json",
                            color="info",
                            size="sm",
                            className="w-100"
                        )
                    ], className="compact-body")
                ])
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-crosshairs me-2"),
                        "Разметка полей",
                        dbc.Badge(id="markup-status-badge", color="secondary", children="Готов", className="ms-2")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(
                            id='markup-interactive-image',
                            config={
                                'displayModeBar': True,
                                'displaylogo': False,
                                'modeBarButtonsToAdd': ['drawrect', 'eraseshape'],
                                'modeBarButtonsToRemove': ['lasso2d', 'select2d']
                            },
                            style={'height': '70vh'}
                        ),
                        html.Div(id="markup-coordinates-display", className="mt-3")
                    ])
                ], className="mb-3 result-card")
            ], width=9)
        ])
    ])



def create_batch_processing_tab() -> html.Div:
    """Режим пакетной обработки"""
    return html.Div([
        dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            "Загрузите несколько PDF для одновременной обработки"
        ], color="info", className="mb-3"),
        
        dbc.Card([
            dbc.CardHeader("Пакетная загрузка"),
            dbc.CardBody([
                dcc.Upload(
                    id='batch-upload',
                    children=dbc.Alert([
                        html.I(className="fas fa-folder-open fa-3x mb-3"),
                        html.Br(),
                        html.H5("Перетащите несколько PDF")
                    ], color="light", className="text-center py-5 upload-area"),
                    style={'borderWidth': '3px', 'borderStyle': 'dashed', 'borderRadius': '10px', 'cursor': 'pointer'},
                    multiple=True
                ),
                html.Hr(),
                dbc.Row([
                    dbc.Col([
                        dcc.Dropdown(
                            id='batch-config-select',
                            options=get_config_options_grouped(),
                            placeholder="Тип документов",
                            className="compact-dropdown"
                        )
                    ], width=8),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-cogs me-2"), "Обработать"],
                            id="batch-process-btn",
                            color="primary",
                            size="lg",
                            className="w-100",
                            disabled=True
                        )
                    ], width=4)
                ])
            ])
        ])
    ])



def get_config_options_grouped() -> List[Dict]:
    """Получение опций БЕЗ разделителей, компактный формат"""
    configs = get_available_configs()
    
    options = []
    
    for c in configs:
        name = c['name']
        
        # Сокращаем названия
        name = name.replace('о повышении квалификации', 'ПК')
        name = name.replace('о профессиональной переподготовке', 'ПП')
        name = name.replace('Удостоверение', 'Уд.')
        name = name.replace('Диплом', 'Дип.')
        name = name.replace('(вариант 1)', 'v1')
        name = name.replace('(вариант 2)', 'v2')
        name = name.replace('Финансового университета', 'ФинУнив.')
        
        # Убираем лишние скобки
        name = name.replace('(', '').replace(')', '')
        
        # Префикс организации
        org_prefix = {
            '1T': '1Т',
            'ROSNOU': 'РОСНОУ',
            'FINUNIVERSITY': 'ФинУнив.'
        }.get(c['organization'], c['organization'])
        
        options.append({
            'label': f"{name} {org_prefix}",
            'value': c['id']
        })
    
    return options



def create_interactive_plotly_image(img: Image.Image, boxes: Dict = None) -> go.Figure:
    """Создание интерактивного изображения"""
    img_array = np.array(img)
    
    fig = go.Figure()
    fig.add_trace(go.Image(z=img_array))
    
    if boxes:
        colors = ['red', 'green', 'blue', 'orange', 'purple', 'cyan']
        for i, (field_name, box) in enumerate(boxes.items()):
            if box and len(box) == 4:
                x0, y0, x1, y1 = box
                color = colors[i % len(colors)]
                
                fig.add_shape(
                    type="rect",
                    x0=x0, y0=y0, x1=x1, y1=y1,
                    line=dict(color=color, width=3)
                )
                
                fig.add_annotation(
                    x=x0, y=y0,
                    text=get_field_description(field_name),
                    showarrow=False,
                    bgcolor=color,
                    font=dict(color='white', size=10),
                    yshift=-10
                )
    
    fig.update_layout(
        dragmode='drawrect',
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
    
    # Callback: Загрузка PDF
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
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            images = image_processor.convert_pdf_from_bytes(decoded)
            
            if not images:
                return None, None, True, dbc.Alert("Ошибка загрузки", color="danger", className="small")
            
            images_b64 = []
            for img in images:
                img_resized = image_processor.resize_image(img)
                buffer = io.BytesIO()
                img_resized.save(buffer, format='PNG')
                img_b64 = base64.b64encode(buffer.getvalue()).decode()
                images_b64.append(img_b64)
            
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
            
            return preview, images_b64, False, dbc.Alert(f"✓ {len(images)} стр.", color="success", className="small")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            return None, None, True, dbc.Alert(f"Ошибка: {str(e)}", color="danger", className="small")
    
    # Callback: Поворот
    @app.callback(
        [Output('rotation-angle-store', 'data'),
         Output('rotation-status', 'children'),
         Output('quick-rotation-btn', 'children'),
         Output('quick-preview-panel', 'children', allow_duplicate=True)],
        [Input('quick-rotation-btn', 'n_clicks')],
        [State('rotation-angle-store', 'data'),
         State('global-pdf-store', 'data'),
         State('quick-upload', 'filename'),
         State('quick-config-select', 'value')],
        prevent_initial_call=True
    )
    def rotate_image_and_preview(n_clicks, current_angle, pdf_data, filename, config_id):
        if not n_clicks or not pdf_data:
            raise PreventUpdate
        
        new_angle = (current_angle + 90) % 360
        icons = {0: "→", 90: "↓", 180: "←", 270: "↑"}
        
        try:
            img_data = base64.b64decode(pdf_data[0])
            img = Image.open(io.BytesIO(img_data))
            
            if new_angle:
                img = image_processor.rotate_image(img, new_angle)
            
            if config_id:
                config = get_config(config_id)
                img = doc_processor.display_image_with_boxes(img, config.fields)
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            badges = [dbc.Badge(f"{new_angle}°", color="warning", className="ms-2")]
            if config_id:
                config = get_config(config_id)
                badges.append(dbc.Badge(config.name[:30], color="info", className="ms-2"))
            
            preview = dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-file-pdf me-2"),
                    f"{filename}"
                ] + badges),
                dbc.CardBody([
                    html.Img(
                        src=f"data:image/png;base64,{img_b64}",
                        style={'width': '100%', 'maxHeight': '600px', 'objectFit': 'contain'},
                        className="border rounded"
                    )
                ])
            ], className="result-card")
            
            return new_angle, f"{new_angle}°", [
                html.I(className="fas fa-redo me-2"), 
                f"90° {icons.get(new_angle, '')}"
            ], preview
            
        except Exception as e:
            logger.error(f"Ошибка поворота: {e}")
            raise PreventUpdate
    
    # Callback: Отображение полей
    @app.callback(
        Output('quick-preview-panel', 'children', allow_duplicate=True),
        [Input('quick-config-select', 'value')],
        [State('global-pdf-store', 'data'),
         State('quick-upload', 'filename'),
         State('rotation-angle-store', 'data')],
        prevent_initial_call=True
    )
    def show_fields_on_config_select(config_id, pdf_data, filename, rotation):
        if not config_id or not pdf_data:
            raise PreventUpdate
        
        try:
            config = get_config(config_id)
            
            img_data = base64.b64decode(pdf_data[0])
            img = Image.open(io.BytesIO(img_data))
            
            if rotation:
                img = image_processor.rotate_image(img, rotation)
            
            img_with_boxes = doc_processor.display_image_with_boxes(img, config.fields)
            
            buffer = io.BytesIO()
            img_with_boxes.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            badges = [dbc.Badge(config.name[:30], color="info", className="ms-2")]
            if rotation:
                badges.append(dbc.Badge(f"{rotation}°", color="warning", className="ms-2"))
            
            preview = dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-file-pdf me-2"),
                    f"{filename}"
                ] + badges),
                dbc.CardBody([
                    html.Img(
                        src=f"data:image/png;base64,{img_b64}",
                        style={'width': '100%', 'maxHeight': '600px', 'objectFit': 'contain'},
                        className="border rounded"
                    ),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        f"Поля: {len(config.fields)}"
                    ], className="text-muted d-block mt-2")
                ])
            ], className="result-card")
            
            return preview
            
        except Exception as e:
            logger.error(f"Ошибка отображения полей: {e}")
            raise PreventUpdate
    
    # Callback: Распознавание
    @app.callback(
        [Output('quick-results-panel', 'children'),
         Output('quick-progress-panel', 'children'),
         Output('global-results-store', 'data')],
        [Input('quick-run-btn', 'n_clicks')],
        [State('global-pdf-store', 'data'),
         State('quick-config-select', 'value'),
         State('rotation-angle-store', 'data'),
         State('quick-enhance-check', 'value')]
    )
    def quick_run_ocr(n_clicks, pdf_data, config_id, rotation, enhance):
        if not n_clicks or not pdf_data or not config_id:
            raise PreventUpdate
        
        try:
            config = get_config(config_id)
            uncertainty_engine = UncertaintyEngine(config.organization)
            
            all_results = []
            
            for page_num, img_b64 in enumerate(pdf_data):
                img_data = base64.b64decode(img_b64)
                img = Image.open(io.BytesIO(img_data))
                
                if rotation:
                    img = image_processor.rotate_image(img, rotation)
                
                if enhance and 1 in enhance:
                    img = image_processor.enhance_image_advanced(img)
                
                result = doc_processor.extract_fields(img, config, uncertainty_engine)
                result['page'] = page_num + 1
                
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
            
            results_ui = create_results_interface(all_results, config)
            
            return results_ui, dbc.Alert(f"✓ {len(pdf_data)} стр.", color="success"), all_results
            
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}", exc_info=True)
            return dbc.Alert(f"Ошибка: {str(e)}", color="danger"), "", None
    
    # Callback: Обновление поля
    @app.callback(
        Output('global-results-store', 'data', allow_duplicate=True),
        [Input({'type': 'field-input', 'page': ALL, 'field': ALL}, 'value')],
        [State('global-results-store', 'data'),
         State({'type': 'field-input', 'page': ALL, 'field': ALL}, 'id')],
        prevent_initial_call=True
    )
    def update_field_values(values, current_results, ids):
        if not current_results or not values:
            raise PreventUpdate
        
        try:
            for i, (value, id_dict) in enumerate(zip(values, ids)):
                page_idx = id_dict['page'] - 1
                field_name = id_dict['field']
                
                if page_idx < len(current_results):
                    current_results[page_idx][field_name] = value
            
            return current_results
        except Exception as e:
            logger.error(f"Ошибка обновления полей: {e}")
            raise PreventUpdate
    
    # Callback: Одобрение страницы (применение изменений)
    @app.callback(
        Output({'type': 'page-approval-status', 'page': MATCH}, 'children'),
        [Input({'type': 'approve-page-btn', 'page': MATCH}, 'n_clicks')],
        [State('global-results-store', 'data'),
         State({'type': 'approve-page-btn', 'page': MATCH}, 'id')],
        prevent_initial_call=True
    )
    def approve_page(n_clicks, results, btn_id):
        if not n_clicks:
            raise PreventUpdate
        
        page_num = btn_id['page']
        return dbc.Alert([
            html.I(className="fas fa-check-circle me-2"), 
            f"Страница {page_num} одобрена"
        ], color="success", className="small mt-2")
    
    # Callback: Одобрение всех (применение всех изменений)
    @app.callback(
        [Output('all-pages-approval-status', 'children'),
         Output('json-editor-store', 'data')],
        [Input('approve-all-pages-btn', 'n_clicks')],
        [State('global-results-store', 'data')],
        prevent_initial_call=True
    )
    def approve_all_pages(n_clicks, results):
        if not n_clicks or not results:
            raise PreventUpdate
        
        # Обновляем JSON для редактора
        json_data = json.dumps(results, ensure_ascii=False, indent=2)
        
        return dbc.Alert([
            html.I(className="fas fa-check-double me-2"), 
            f"Все {len(results)} стр. одобрены"
        ], color="success"), json_data
    
    # Callback: Интерактивная разметка
    @app.callback(
        [Output('markup-interactive-image', 'figure'),
         Output('current-image-store', 'data'),
         Output('markup-upload-info', 'children')],
        [Input('markup-upload', 'contents'),
         Input('markup-base-config', 'value')],
        [State('markup-upload', 'filename')]
    )
    def update_interactive_image(contents, base_config, filename):
        if not contents:
            return go.Figure(), None, ""
        
        try:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            images = image_processor.convert_pdf_from_bytes(decoded)
            img = images[0]
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            boxes = {}
            if base_config and base_config != 'empty':
                config = get_config(base_config)
                for field in config.fields:
                    boxes[field['name']] = field.get('box')
            
            fig = create_interactive_plotly_image(img, boxes)
            
            return fig, img_b64, dbc.Alert(f"✓ {filename} ({img.size[0]}×{img.size[1]}px)", color="success", className="small")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            return go.Figure(), None, dbc.Alert(f"Ошибка: {str(e)}", color="danger", className="small")
    
    # Callback: Координаты
    @app.callback(
        [Output('markup-coordinates-display', 'children'),
         Output('markup-status-badge', 'children'),
         Output('markup-status-badge', 'color')],
        [Input('markup-interactive-image', 'relayoutData')]
    )
    def display_drawn_coordinates(relayout_data):
        if not relayout_data or 'shapes' not in relayout_data:
            return "", "Готов", "secondary"
        
        shapes = relayout_data['shapes']
        if shapes:
            coords_info = []
            for i, shape in enumerate(shapes):
                if shape['type'] == 'rect':
                    coords_info.append(
                        html.Li(f"Область {i+1}: ({int(shape['x0'])}, {int(shape['y0'])}, {int(shape['x1'])}, {int(shape['y1'])})")
                    )
            
            if coords_info:
                return dbc.Alert([
                    html.H6("Области:"),
                    html.Ul(coords_info, className="mb-0")
                ], color="info"), f"{len(shapes)}", "success"
        
        return "", "Рисуйте", "warning"
    
    # Callback для JSON редактора (ПЕРЕМЕЩЁН СЮДА)
    @app.callback(
        Output('json-editor-panel', 'children'),
        [Input('edit-json-btn', 'n_clicks')],
        [State('global-results-store', 'data')],
        prevent_initial_call=True
    )
    def show_json_editor(n_clicks, results):
        if not n_clicks or not results:
            raise PreventUpdate
        
        json_str = json.dumps(results, ensure_ascii=False, indent=2)
        
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-code me-2"),
                "JSON Редактор"
            ]),
            dbc.CardBody([
                dcc.Textarea(
                    id='json-textarea',
                    value=json_str,
                    style={'width': '100%', 'height': '400px', 'fontFamily': 'monospace'},
                    className="form-control"
                ),
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-save me-2"), "Применить изменения"],
                            id='apply-json-btn',
                            color="primary",
                            size="sm",
                            className="mt-2"
                        )
                    ], width=3),
                    dbc.Col([
                        html.Div(id='json-status')
                    ], width=9)
                ])
            ])
        ], className="mb-3 result-card")
    
    # Callback для применения JSON изменений (ПЕРЕМЕЩЁН СЮДА)
    @app.callback(
        [Output('global-results-store', 'data', allow_duplicate=True),
         Output('json-status', 'children')],
        [Input('apply-json-btn', 'n_clicks')],
        [State('json-textarea', 'value')],
        prevent_initial_call=True
    )
    def apply_json_changes(n_clicks, json_str):
        if not n_clicks:
            raise PreventUpdate
        
        try:
            new_results = json.loads(json_str)
            return new_results, dbc.Alert("✓ Изменения применены", color="success", className="mt-2")
        except json.JSONDecodeError as e:
            return no_update, dbc.Alert(f"❌ Ошибка JSON: {str(e)}", color="danger", className="mt-2")



def create_results_interface(results: List[Dict], config) -> html.Div:
    """Создание интерфейса результатов"""
    pages = [create_editable_page_table(r, config) for r in results]
    
    return html.Div([
        create_summary_panel(results, config),
        html.Hr()
    ] + pages + [
        # Кнопка "Одобрить всё" внизу
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-check-double me-2"), "Одобрить всё"],
                            id='approve-all-pages-btn',
                            color="success",
                            size="lg",
                            className="w-100"
                        ),
                        html.Div(id='all-pages-approval-status', className="mt-2")
                    ], width=6),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-edit me-2"), "Редактировать JSON"],
                            id='edit-json-btn',
                            color="info",
                            size="lg",
                            className="w-100"
                        )
                    ], width=6)
                ])
            ])
        ], className="mb-3 result-card"),
        
        # JSON редактор
        html.Div(id='json-editor-panel')
    ])



def create_editable_page_table(page_result: Dict, config) -> dbc.Card:
    """Таблица с ШИРОКИМ превью (50%) и узким полем значения (38%)"""
    page_num = page_result['page']
    uncertainties = page_result.get('uncertainties', [])
    uncertain_fields = {u['field'] for u in uncertainties}
    field_thumbnails = page_result.get('field_thumbnails', {})
    
    table_rows = []
    
    for field_config in config.fields:
        field_name = field_config['name']
        
        if field_name == 'series_and_number':
            series_value = page_result.get('series', '')
            thumb_b64 = field_thumbnails.get(field_name, '')
            is_uncertain = field_name in uncertain_fields
            
            table_rows.append(html.Tr([
                html.Td([
                    html.I(className="fas fa-exclamation-triangle text-warning me-1") if is_uncertain else "",
                    "Серия"
                ], style={'width': '12%', 'fontSize': '0.9rem'}),
                html.Td([
                    html.Img(
                        src=f"data:image/png;base64,{thumb_b64}",
                        style={'maxWidth': '100%', 'maxHeight': '150px', 'objectFit': 'contain'},
                        className="border"
                    ) if thumb_b64 else "—"
                ], style={'width': '50%', 'textAlign': 'center'}, rowSpan=2),
                html.Td([
                    dcc.Input(
                        id={'type': 'field-input', 'page': page_num, 'field': 'series'},
                        value=str(series_value),
                        style={
                            'width': '100%', 
                            'backgroundColor': '#fff3cd' if is_uncertain else '#fff',
                            'padding': '6px 10px',
                            'fontSize': '0.9rem'
                        },
                        className="form-control form-control-sm"
                    )
                ], style={'width': '38%'})
            ], className="table-warning" if is_uncertain else ""))
            
            number_value = page_result.get('number', '')
            
            table_rows.append(html.Tr([
                html.Td([
                    html.I(className="fas fa-exclamation-triangle text-warning me-1") if is_uncertain else "",
                    "Номер"
                ], style={'width': '12%', 'fontSize': '0.9rem'}),
                html.Td([
                    dcc.Input(
                        id={'type': 'field-input', 'page': page_num, 'field': 'number'},
                        value=str(number_value),
                        style={
                            'width': '100%', 
                            'backgroundColor': '#fff3cd' if is_uncertain else '#fff',
                            'padding': '6px 10px',
                            'fontSize': '0.9rem'
                        },
                        className="form-control form-control-sm"
                    )
                ], style={'width': '38%'})
            ], className="table-warning" if is_uncertain else ""))
        
        else:
            field_display = get_field_description(field_name)
            value = page_result.get(field_name, '')
            thumb_b64 = field_thumbnails.get(field_name, '')
            is_uncertain = field_name in uncertain_fields
            
            table_rows.append(html.Tr([
                html.Td([
                    html.I(className="fas fa-exclamation-triangle text-warning me-1") if is_uncertain else "",
                    field_display
                ], style={'width': '12%', 'fontSize': '0.9rem'}),
                html.Td([
                    html.Img(
                        src=f"data:image/png;base64,{thumb_b64}",
                        style={'maxWidth': '100%', 'maxHeight': '150px', 'objectFit': 'contain'},
                        className="border"
                    ) if thumb_b64 else "—"
                ], style={'width': '50%', 'textAlign': 'center'}),
                html.Td([
                    dcc.Input(
                        id={'type': 'field-input', 'page': page_num, 'field': field_name},
                        value=str(value),
                        style={
                            'width': '100%', 
                            'backgroundColor': '#fff3cd' if is_uncertain else '#fff',
                            'padding': '6px 10px',
                            'fontSize': '0.9rem'
                        },
                        className="form-control form-control-sm"
                    )
                ], style={'width': '38%'})
            ], className="table-warning" if is_uncertain else ""))
    
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-file-alt me-2"), 
            f"Страница {page_num}"
        ]),
        dbc.CardBody([
            dbc.Table([
                html.Thead([html.Tr([
                    html.Th("Поле", style={'fontSize': '0.85rem', 'width': '12%'}),
                    html.Th("Превью", style={'fontSize': '0.85rem', 'width': '50%'}),
                    html.Th("Значение", style={'fontSize': '0.85rem', 'width': '38%'})
                ])]),
                html.Tbody(table_rows)
            ], bordered=True, hover=True, size='sm'),
            
            # Кнопка "Одобрить" НИЖЕ таблицы
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        [html.I(className="fas fa-check me-2"), f"Одобрить страницу {page_num}"],
                        id={'type': 'approve-page-btn', 'page': page_num},
                        color="success",
                        size="sm",
                        className="w-100 mt-2"
                    ),
                    html.Div(id={'type': 'page-approval-status', 'page': page_num})
                ])
            ])
        ])
    ], className="mb-3 result-card")



def create_summary_panel(results: List[Dict], config) -> dbc.Card:
    """Создание сводной панели"""
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
        dbc.CardHeader([html.I(className="fas fa-chart-bar me-2"), "Сводка"]),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H4(f"{total_pages}"),
                    html.P("Страниц", className="small text-muted"),
                    html.Hr(),
                    html.P(f"📋 {config.name[:40]}", className="small"),
                    html.P([
                        html.I(className="fas fa-exclamation-triangle text-warning me-1") if total_uncertainties > 0 else html.I(className="fas fa-check-circle text-success me-1"),
                        f"{total_uncertainties} проверки" if total_uncertainties > 0 else "Всё ОК"
                    ], className="small")
                ], width=6),
                dbc.Col([
                    html.A(
                        dbc.Button([html.I(className="fas fa-file-csv me-2"), "CSV"], color="success", size="sm", className="w-100 mb-2"),
                        href=f"data:text/csv;charset=utf-8;base64,{csv_b64}",
                        download=f"ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    ),
                    html.A(
                        dbc.Button([html.I(className="fas fa-file-code me-2"), "JSON"], color="info", size="sm", className="w-100"),
                        href=f"data:application/json;base64,{json_b64}",
                        download=f"ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    )
                ], width=6)
            ])
        ])
    ], className="mb-4 result-card")



if __name__ == '__main__':
    app = create_dash_app()
    app.run(debug=True, port=8050)
