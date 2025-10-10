"""
Инструмент интерактивной разметки полей документов
Версия: 3.0 (Упрощенная и исправленная)
"""

import dash
from dash import dcc, html, Input, Output, State, ALL, MATCH
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MarkupTool:
    """Инструмент для разметки полей документов"""
    
    def __init__(self):
        self.default_fields = [
            {'name': 'full_name', 'display_name': 'ФИО'},
            {'name': 'series_and_number', 'display_name': 'Серия и номер'},
            {'name': 'registration_number', 'display_name': 'Регистрационный номер'},
            {'name': 'issue_date', 'display_name': 'Дата выдачи'}
        ]
        
        self.colors = {
            'full_name': '#FF6B6B',
            'series_and_number': '#4ECDC4',
            'registration_number': '#FFEAA7',
            'issue_date': '#DFE6E9'
        }
        
        logger.info("MarkupTool инициализирован")
    
    def create_markup_layout(self) -> html.Div:
        """Создание layout для разметки"""
        return html.Div([
            dbc.Alert([
                html.H4([
                    html.I(className="fas fa-crosshairs me-2"),
                    "Инструмент разметки полей"
                ]),
                html.P("Создайте новую конфигурацию или отредактируйте существующую", className="mb-0")
            ], color="info", className="mb-4"),
            
            dbc.Card([
                dbc.CardHeader("Настройка конфигурации"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Название:"),
                            dbc.Input(
                                id='markup-config-name',
                                placeholder="Например: МГУ - Диплом 2024"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Организация:"),
                            dbc.Input(
                                id='markup-org-name',
                                placeholder="Например: MSU"
                            )
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Тип документа:"),
                            dcc.Dropdown(
                                id='markup-doc-type',
                                options=[
                                    {'label': 'Диплом', 'value': 'diploma'},
                                    {'label': 'Удостоверение', 'value': 'certificate'},
                                    {'label': 'Другой', 'value': 'other'}
                                ],
                                placeholder="Выберите тип"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Базовая конфигурация:"),
                            dcc.Dropdown(
                                id='markup-base-config-select',
                                options=[
                                    {'label': 'Пустая', 'value': 'empty'},
                                    {'label': '1Т - Удостоверение', 'value': '1T_CERTIFICATE'},
                                    {'label': '1Т - Диплом', 'value': '1T_DIPLOMA'},
                                    {'label': 'РОСНОУ - Диплом', 'value': 'ROSNOU_DIPLOMA'},
                                ],
                                value='empty'
                            )
                        ], width=6)
                    ])
                ])
            ], className="mb-4"),
            
            dbc.Card([
                dbc.CardHeader("Загрузка образца"),
                dbc.CardBody([
                    dcc.Upload(
                        id='markup-upload-sample',
                        children=dbc.Alert([
                            html.I(className="fas fa-file-pdf fa-2x mb-3"),
                            html.Br(),
                            html.H5("Загрузите PDF образец")
                        ], color="light", className="text-center py-4"),
                        style={
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '10px',
                            'cursor': 'pointer'
                        },
                        multiple=False,
                        accept='.pdf'
                    )
                ])
            ], className="mb-4"),
            
            html.Div(id='markup-image-panel', className="mb-4"),
            
            dbc.Card([
                dbc.CardHeader("Разметка полей"),
                dbc.CardBody([
                    html.P([
                        html.I(className="fas fa-info-circle me-2"),
                        "Введите координаты полей вручную или используйте визуальный редактор"
                    ], className="text-muted small"),
                    html.Div(id='markup-fields-list'),
                    dbc.Button(
                        [html.I(className="fas fa-plus me-2"), "Добавить поле"],
                        id='add-field-markup-btn',
                        color="secondary",
                        outline=True,
                        size="sm",
                        className="mt-2"
                    )
                ])
            ], className="mb-4"),
            
            html.Div(id='markup-preview-section', className="mb-4"),
            
            dbc.Card([
                dbc.CardHeader("Экспорт конфигурации"),
                dbc.CardBody([
                    dbc.Button(
                        [html.I(className="fas fa-eye me-2"), "Предпросмотр"],
                        id='preview-markup-btn',
                        color="info",
                        className="me-2"
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-download me-2"), "Экспорт Python код"],
                        id='export-markup-btn',
                        color="success"
                    )
                ])
            ]),
            
            dcc.Store(id='markup-image-data-store'),
            dcc.Store(id='markup-boxes-data-store', data={}),
            dcc.Store(id='markup-fields-data-store', data=[]),
            
            dbc.Modal([
                dbc.ModalHeader("Python код конфигурации"),
                dbc.ModalBody([
                    html.Pre(id='config-python-code', style={'whiteSpace': 'pre-wrap', 'fontSize': '0.85rem'})
                ]),
                dbc.ModalFooter([
                    dbc.Button("Копировать", id='copy-code-markup-btn', color="primary"),
                    dbc.Button("Закрыть", id='close-modal-markup', color="secondary")
                ])
            ], id='export-modal-markup', size="xl")
        ])
    
    def create_field_editor(self, field_name: str, field_display: str, 
                           box: Optional[Tuple] = None, color: str = '#000000') -> dbc.Card:
        """Создание редактора для поля"""
        return dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div(
                                style={
                                    'width': '20px',
                                    'height': '20px',
                                    'backgroundColor': color,
                                    'border': '1px solid #000',
                                    'display': 'inline-block',
                                    'marginRight': '10px'
                                }
                            ),
                            html.Strong(field_display)
                        ])
                    ], width=3),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("X1"),
                            dbc.Input(
                                id={'type': 'box-x1-markup', 'field': field_name},
                                type='number',
                                value=box[0] if box else 0,
                                size='sm'
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("Y1"),
                            dbc.Input(
                                id={'type': 'box-y1-markup', 'field': field_name},
                                type='number',
                                value=box[1] if box else 0,
                                size='sm'
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("X2"),
                            dbc.Input(
                                id={'type': 'box-x2-markup', 'field': field_name},
                                type='number',
                                value=box[2] if box else 100,
                                size='sm'
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("Y2"),
                            dbc.Input(
                                id={'type': 'box-y2-markup', 'field': field_name},
                                type='number',
                                value=box[3] if box else 100,
                                size='sm'
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.Button(
                            html.I(className="fas fa-trash"),
                            id={'type': 'delete-field-markup', 'field': field_name},
                            color="danger",
                            size="sm",
                            outline=True
                        )
                    ], width=1)
                ], className="align-items-center")
            ])
        ], className="mb-2")
    
    def draw_boxes_on_image(self, img: Image.Image, boxes: Dict[str, Tuple]) -> Image.Image:
        """Отрисовка рамок полей на изображении"""
        img_with_boxes = img.copy()
        draw = ImageDraw.Draw(img_with_boxes)
        
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        for field_name, box in boxes.items():
            if not box or len(box) != 4:
                continue
            
            color = self.colors.get(field_name, '#000000')
            
            draw.rectangle(box, outline=color, width=3)
            
            field_display = next(
                (f['display_name'] for f in self.default_fields if f['name'] == field_name),
                field_name
            )
            
            text_x, text_y = box[0], max(0, box[1] - 25)
            
            try:
                text_bbox = draw.textbbox((text_x, text_y), field_display, font=font)
                draw.rectangle(text_bbox, fill=color)
                draw.text((text_x, text_y), field_display, fill='white', font=font)
            except:
                pass
        
        return img_with_boxes
    
    def export_to_config_format(self, config_data: Dict) -> str:
        """Экспорт в формат конфигурации Python"""
        config_name = config_data.get('name', 'CustomConfig')
        org = config_data.get('organization', 'CUSTOM')
        doc_type = config_data.get('document_type', 'custom')
        fields = config_data.get('fields', [])
        
        code = f'''
# Конфигурация: {config_name}
# Автоматически сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

'{org}_{doc_type.upper()}': DocumentConfig(
    name='{config_name}',
    organization='{org}',
    document_type='{doc_type}',
    fields=[
'''
        
        for field in fields:
            code += f'''        {{'name': '{field['name']}', 'box': {field['box']}}},
'''
        
        code += f'''    ],
    patterns={{
        'series_and_number': {org}Parsers.parse_series_number,
        'registration_number': {org}Parsers.parse_reg_number,
        'full_name': lambda x: (x.strip(), len(x.strip()) < 5),
        'issue_date': CommonParsers.parse_date_standard
    }},
    ocr_params={{'scale_factor': 3, 'contrast_boost': 1.5}}
)
'''
        
        return code


def setup_markup_callbacks(app, markup_tool: MarkupTool):
    """Настройка callbacks для инструмента разметки"""
    
    # Callback: Загрузка изображения
    @app.callback(
        [Output('markup-image-panel', 'children'),
         Output('markup-image-data-store', 'data')],
        [Input('markup-upload-sample', 'contents')],
        [State('markup-upload-sample', 'filename')]
    )
    def load_markup_image(contents, filename):
        if not contents:
            return "", None
        
        try:
            from core.image_processor import AdvancedImageProcessor
            
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            processor = AdvancedImageProcessor(max_dimension=1200)
            images = processor.convert_pdf_from_bytes(decoded)
            
            if not images:
                return dbc.Alert("Ошибка загрузки PDF", color="danger"), None
            
            img = images[0]
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            panel = dbc.Card([
                dbc.CardHeader(f"Образец: {filename} ({img.size[0]}×{img.size[1]}px)"),
                dbc.CardBody([
                    html.Img(
                        id='markup-main-image-display',
                        src=f"data:image/png;base64,{img_b64}",
                        style={'width': '100%', 'height': 'auto', 'border': '2px solid #007bff'}
                    ),
                    html.Small(
                        "Координаты указываются для финального размера после обработки (DPI=300, resize до 1200px)",
                        className="text-muted d-block mt-2"
                    )
                ])
            ])
            
            return panel, img_b64
            
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            return dbc.Alert(f"Ошибка: {str(e)}", color="danger"), None
    
    # Callback: Инициализация полей
    @app.callback(
        [Output('markup-fields-list', 'children'),
         Output('markup-fields-data-store', 'data')],
        [Input('markup-base-config-select', 'value')],
        [State('markup-fields-data-store', 'data')]
    )
    def initialize_fields(base_config, current_fields):
        if base_config == 'empty':
            fields = []
            for field_def in markup_tool.default_fields:
                fields.append({
                    'name': field_def['name'],
                    'display_name': field_def['display_name'],
                    'box': None
                })
        else:
            try:
                from core.config import get_config
                config = get_config(base_config)
                
                fields = []
                for field_config in config.fields:
                    fields.append({
                        'name': field_config['name'],
                        'display_name': field_config.get('display_name', field_config['name']),
                        'box': field_config.get('box')
                    })
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации: {e}")
                fields = []
        
        field_editors = []
        for field in fields:
            editor = markup_tool.create_field_editor(
                field['name'],
                field['display_name'],
                field.get('box'),
                markup_tool.colors.get(field['name'], '#000000')
            )
            field_editors.append(editor)
        
        return field_editors, fields
    
    # Callback: Предпросмотр конфигурации
    @app.callback(
        Output('markup-preview-section', 'children'),
        [Input('preview-markup-btn', 'n_clicks')],
        [State('markup-image-data-store', 'data'),
         State({'type': 'box-x1-markup', 'field': ALL}, 'value'),
         State({'type': 'box-y1-markup', 'field': ALL}, 'value'),
         State({'type': 'box-x2-markup', 'field': ALL}, 'value'),
         State({'type': 'box-y2-markup', 'field': ALL}, 'value'),
         State({'type': 'box-x1-markup', 'field': ALL}, 'id'),
         State('markup-fields-data-store', 'data')]
    )
    def preview_configuration(n_clicks, img_b64, x1_values, y1_values, x2_values, y2_values, field_ids, fields):
        if not n_clicks or not img_b64:
            return html.Div()
        
        try:
            img_data = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_data))
            
            boxes = {}
            for i, field_id in enumerate(field_ids):
                field_name = field_id['field']
                if all(v is not None for v in [x1_values[i], y1_values[i], x2_values[i], y2_values[i]]):
                    boxes[field_name] = (
                        int(x1_values[i]),
                        int(y1_values[i]),
                        int(x2_values[i]),
                        int(y2_values[i])
                    )
            
            img_with_boxes = markup_tool.draw_boxes_on_image(img, boxes)
            
            buffer = io.BytesIO()
            img_with_boxes.save(buffer, format='PNG')
            preview_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            return dbc.Card([
                dbc.CardHeader("Предпросмотр конфигурации"),
                dbc.CardBody([
                    html.Img(
                        src=f"data:image/png;base64,{preview_b64}",
                        style={'width': '100%', 'height': 'auto'}
                    )
                ])
            ])
            
        except Exception as e:
            logger.error(f"Ошибка предпросмотра: {e}")
            return dbc.Alert(f"Ошибка: {str(e)}", color="danger")
    
    # Callback: Экспорт конфигурации
    @app.callback(
        [Output('export-modal-markup', 'is_open'),
         Output('config-python-code', 'children')],
        [Input('export-markup-btn', 'n_clicks'),
         Input('close-modal-markup', 'n_clicks')],
        [State('markup-config-name', 'value'),
         State('markup-org-name', 'value'),
         State('markup-doc-type', 'value'),
         State({'type': 'box-x1-markup', 'field': ALL}, 'value'),
         State({'type': 'box-y1-markup', 'field': ALL}, 'value'),
         State({'type': 'box-x2-markup', 'field': ALL}, 'value'),
         State({'type': 'box-y2-markup', 'field': ALL}, 'value'),
         State({'type': 'box-x1-markup', 'field': ALL}, 'id'),
         State('markup-fields-data-store', 'data'),
         State('export-modal-markup', 'is_open')]
    )
    def export_configuration(n_export, n_close, config_name, org_name, doc_type,
                           x1_values, y1_values, x2_values, y2_values, field_ids, fields, is_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            return False, ""
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'close-modal-markup':
            return False, ""
        
        if button_id == 'export-markup-btn':
            config_data = {
                'name': config_name or 'Без названия',
                'organization': org_name or 'CUSTOM',
                'document_type': doc_type or 'custom',
                'fields': []
            }
            
            for i, field_id in enumerate(field_ids):
                field_name = field_id['field']
                field_display = next(
                    (f['display_name'] for f in fields if f['name'] == field_name),
                    field_name
                )
                
                if all(v is not None for v in [x1_values[i], y1_values[i], x2_values[i], y2_values[i]]):
                    config_data['fields'].append({
                        'name': field_name,
                        'display_name': field_display,
                        'box': (
                            int(x1_values[i]),
                            int(y1_values[i]),
                            int(x2_values[i]),
                            int(y2_values[i])
                        )
                    })
            
            code = markup_tool.export_to_config_format(config_data)
            
            return True, code
        
        return is_open, ""
