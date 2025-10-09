"""
Dash Dashboard для OCR платформы
"""

import dash
from dash import dcc, html, Input, Output, State, ALL, MATCH, callback_context
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate

from PIL import Image
import pandas as pd
import io
import base64
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.ocr_engine import DocumentProcessor, ImageProcessor
from core.config import get_config, get_available_configs, UncertaintyEngine, get_field_description

logger = logging.getLogger(__name__)


def create_dash_app(tesseract_cmd: Optional[str] = None):
    """
    Создание Dash приложения
    
    Args:
        tesseract_cmd: Путь к Tesseract
        
    Returns:
        Dash приложение
    """
    doc_processor = DocumentProcessor(tesseract_cmd)
    image_processor = ImageProcessor()
    
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
    
    logger.info("Dash приложение инициализировано")
    
    return app


def create_main_layout() -> html.Div:
    """Создание главного layout"""
    return dbc.Container([
        dbc.Alert([
            html.H1("OCR Платформа для документов", className="mb-2"),
            html.P("Распознавание документов об образовании", className="mb-0")
        ], color="primary", className="mb-4"),
        
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-cloud-upload-alt me-2"),
                "Загрузка и настройка"
            ], className="fw-bold"),
            dbc.CardBody([
                dcc.Upload(
                    id='upload-document',
                    children=dbc.Alert([
                        html.I(className="fas fa-cloud-upload-alt fa-3x mb-3 text-primary"),
                        html.Br(),
                        html.H5("Перетащите PDF файл сюда"),
                        html.P("или нажмите для выбора", className="text-muted mb-1")
                    ], color="light", className="text-center py-4 mb-3"),
                    style={
                        'borderWidth': '2px',
                        'borderStyle': 'dashed',
                        'borderRadius': '10px',
                        'cursor': 'pointer'
                    },
                    multiple=False,
                    accept='.pdf'
                ),
                
                html.Hr(),
                
                dbc.Row([
                    dbc.Col([
                        html.Label("Тип документа:", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='config-selector',
                            options=get_config_options(),
                            placeholder="Выберите тип документа"
                        ),
                    ], width=6),
                    
                    dbc.Col([
                        html.Label("Поворот:", className="fw-bold mb-2"),
                        dcc.Dropdown(
                            id='rotation-selector',
                            options=[
                                {'label': '0°', 'value': 0},
                                {'label': '90°', 'value': 90},
                                {'label': '180°', 'value': 180},
                                {'label': '270°', 'value': 270}
                            ],
                            value=0
                        ),
                    ], width=3),
                    
                    dbc.Col([
                        html.Br(),
                        dbc.Button(
                            [html.I(className="fas fa-rocket me-2"), "Запустить OCR"],
                            id="run-ocr-btn",
                            color="success",
                            size="lg",
                            disabled=True,
                            className="w-100"
                        )
                    ], width=3)
                ])
            ])
        ], className="mb-4"),
        
        html.Div(id="status-panel", className="mb-3"),
        html.Div(id="pdf-preview-panel", className="mb-4"),
        html.Div(id="ocr-results-panel"),
        
        dcc.Store(id='pdf-data-store'),
        dcc.Store(id='ocr-results-store'),
        
    ], fluid=True, className="py-4")


def get_config_options() -> List[Dict]:
    """Получение опций конфигураций"""
    configs = get_available_configs()
    return [{'label': f"{c['organization']} - {c['name']}", 'value': c['id']} for c in configs]


def setup_callbacks(app, doc_processor, image_processor):
    """Настройка всех callbacks"""
    
    @app.callback(
        [Output('pdf-data-store', 'data'),
         Output('pdf-preview-panel', 'children'),
         Output('run-ocr-btn', 'disabled'),
         Output('status-panel', 'children')],
        [Input('upload-document', 'contents')],
        [State('upload-document', 'filename')]
    )
    def handle_upload(contents, filename):
        if not contents:
            return None, None, True, ""
        
        try:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            images = image_processor.convert_pdf_from_bytes(decoded)
            
            if not images:
                error = dbc.Alert("Ошибка обработки PDF", color="danger")
                return None, None, True, error
            
            images_b64 = []
            for img in images:
                img_scaled = image_processor.resize_image(img)
                buffer = io.BytesIO()
                img_scaled.save(buffer, format='PNG')
                img_b64 = base64.b64encode(buffer.getvalue()).decode()
                images_b64.append(img_b64)
            
            preview = dbc.Card([
                dbc.CardHeader(f"{filename} - {len(images)} стр."),
                dbc.CardBody([
                    html.Img(
                        src=f"data:image/png;base64,{images_b64[0]}",
                        style={'width': '100%', 'height': 'auto'},
                        className="border"
                    )
                ])
            ])
            
            status = dbc.Alert(
                f"Загружен: {filename} ({len(images)} стр.)",
                color="success"
            )
            
            return images_b64, preview, False, status
            
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            error = dbc.Alert(f"Ошибка: {str(e)}", color="danger")
            return None, None, True, error
    
    @app.callback(
        Output('pdf-preview-panel', 'children', allow_duplicate=True),
        [Input('config-selector', 'value')],
        [State('pdf-data-store', 'data'),
         State('upload-document', 'filename')],
        prevent_initial_call=True
    )
    def show_fields_on_config_select(config_id, pdf_data, filename):
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
                    f"{filename} - 1 стр.",
                    dbc.Badge(f"{config.name}", color="info", className="ms-2")
                ]),
                dbc.CardBody([
                    html.Img(
                        src=f"data:image/png;base64,{img_b64}",
                        style={'width': '100%', 'height': 'auto'},
                        className="border"
                    )
                ])
            ])
            
            return preview
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise PreventUpdate
    
    @app.callback(
        [Output('ocr-results-panel', 'children'),
         Output('ocr-results-store', 'data')],
        [Input('run-ocr-btn', 'n_clicks')],
        [State('pdf-data-store', 'data'),
         State('config-selector', 'value'),
         State('rotation-selector', 'value')]
    )
    def run_ocr(n_clicks, pdf_data, config_id, rotation):
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
            
            return results_ui, all_results
            
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}")
            error = dbc.Alert(f"Ошибка OCR: {str(e)}", color="danger")
            return error, None
    
    @app.callback(
        Output({'type': 'field-status', 'page': MATCH, 'field': MATCH}, 'children'),
        [Input({'type': 'accept-btn', 'page': MATCH, 'field': MATCH}, 'n_clicks')],
        [State({'type': 'field-input', 'page': MATCH, 'field': MATCH}, 'value')],
        prevent_initial_call=True
    )
    def accept_correction(n_clicks, new_value):
        if not n_clicks:
            raise PreventUpdate
        
        return html.Span([
            html.I(className="fas fa-check-circle text-success me-1"),
            "Принято"
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
    """Создание редактируемой таблицы"""
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
        
        row = html.Tr([
            html.Td(field_display, style={'width': '20%'}),
            html.Td([
                html.Img(
                    src=f"data:image/png;base64,{thumb_b64}",
                    style={'maxWidth': '120px', 'maxHeight': '80px'},
                    className="border"
                ) if thumb_b64 else "—"
            ], style={'width': '15%', 'textAlign': 'center'}),
            html.Td([
                dcc.Input(
                    id={'type': 'field-input', 'page': page_num, 'field': field_name},
                    value=str(value),
                    style={'width': '100%', 'backgroundColor': '#fff3cd' if is_uncertain else '#fff'}
                )
            ], style={'width': '45%'}),
            html.Td([
                dbc.Button(
                    "Принять",
                    id={'type': 'accept-btn', 'page': page_num, 'field': field_name},
                    color="success",
                    size="sm"
                ),
                html.Span(
                    id={'type': 'field-status', 'page': page_num, 'field': field_name},
                    className="ms-2"
                )
            ], style={'width': '20%'})
        ], className="table-warning" if is_uncertain else "")
        
        table_rows.append(row)
    
    return dbc.Card([
        dbc.CardHeader(f"Страница {page_num} - Редактирование полей"),
        dbc.CardBody([
            dbc.Table([
                html.Thead([html.Tr([
                    html.Th("Поле"),
                    html.Th("Превью"),
                    html.Th("Значение"),
                    html.Th("Действие")
                ])]),
                html.Tbody(table_rows)
            ], bordered=True, hover=True)
        ])
    ], className="mb-4")


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
    
    return dbc.Card([
        dbc.CardHeader("Сводка результатов"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H5(f"Страниц: {total_pages}"),
                    html.P(f"Конфигурация: {config.name}"),
                    html.P(f"Требуют проверки: {total_uncertainties}" if total_uncertainties > 0 
                          else "Все поля распознаны уверенно")
                ], width=8),
                dbc.Col([
                    html.A(
                        dbc.Button("Скачать CSV", color="success", size="lg", className="w-100"),
                        href=f"data:text/csv;charset=utf-8;base64,{csv_b64}",
                        download=f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    )
                ], width=4)
            ])
        ])
    ], className="mb-4")


if __name__ == '__main__':
    app = create_dash_app()
    app.run(debug=True)
