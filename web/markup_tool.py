"""
Продвинутый инструмент интерактивной разметки полей документов
с визуальным выделением областей и сохранением конфигураций
"""

import dash
from dash import dcc, html, Input, Output, State, ALL, MATCH, callback_context
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class MarkupTool:
    """
    Продвинутый инструмент для разметки полей с визуальным интерфейсом
    """
    
    def __init__(self):
        self.default_fields = [
            {'name': 'fullname', 'display_name': 'ФИО'},
            {'name': 'series', 'display_name': 'Серия'},
            {'name': 'number', 'display_name': 'Номер'},
            {'name': 'seriesandnumber', 'display_name': 'Серия и номер'},
            {'name': 'registrationnumber', 'display_name': 'Регистрационный номер'},
            {'name': 'issuedate', 'display_name': 'Дата выдачи'}
        ]
        
        self.colors = {
            'fullname': '#FF6B6B',
            'series': '#4ECDC4',
            'number': '#45B7D1',
            'seriesandnumber': '#96CEB4',
            'registrationnumber': '#FFEAA7',
            'issuedate': '#DFE6E9'
        }
        
        logger.info("MarkupTool инициализирован")
    
    def create_markup_layout(self) -> html.Div:
        """
        Создание полного layout для разметки
        """
        return html.Div([
            # Заголовок
            dbc.Alert([
                html.H4([
                    html.I(className="fas fa-crosshairs me-2"),
                    "Инструмент разметки полей документов"
                ]),
                html.P("Создайте новую конфигурацию или отредактируйте существующую", className="mb-0")
            ], color="info", className="mb-4"),
            
            # Панель настроек конфигурации
            dbc.Card([
                dbc.CardHeader("Шаг 1: Настройка конфигурации", className="fw-bold"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Название конфигурации:", className="fw-bold"),
                            dbc.Input(
                                id='markup-config-name',
                                placeholder="Например: МойВуз - Диплом 2024",
                                className="mb-2"
                            )
                        ], width=6),
                        
                        dbc.Col([
                            html.Label("Организация:", className="fw-bold"),
                            dbc.Input(
                                id='markup-org-name',
                                placeholder="Например: MYUNIV",
                                className="mb-2"
                            )
                        ], width=6)
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("Тип документа:", className="fw-bold"),
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
                            html.Label("Загрузить базовую конфигурацию:", className="fw-bold"),
                            dcc.Dropdown(
                                id='markup-base-config',
                                options=[
                                    {'label': 'Пустая (с нуля)', 'value': 'empty'},
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
            
            # Панель загрузки образца
            dbc.Card([
                dbc.CardHeader("Шаг 2: Загрузка образца документа", className="fw-bold"),
                dbc.CardBody([
                    dcc.Upload(
                        id='markup-upload',
                        children=dbc.Alert([
                            html.I(className="fas fa-file-pdf fa-3x mb-3 text-primary"),
                            html.Br(),
                            html.H5("Перетащите PDF сюда или нажмите для выбора"),
                            html.Small("Будет использована первая страница для разметки")
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
            
            # Панель с изображением для разметки
            html.Div(id='markup-image-panel', className="mb-4"),
            
            # Панель редактирования полей
            dbc.Card([
                dbc.CardHeader("Шаг 3: Разметка полей", className="fw-bold"),
                dbc.CardBody([
                    html.P([
                        html.I(className="fas fa-info-circle me-2"),
                        "Введите координаты полей вручную или используйте графический редактор для точного выделения"
                    ], className="text-muted small"),
                    
                    html.Div(id='markup-fields-list'),
                    
                    dbc.Button([
                        html.I(className="fas fa-plus me-2"),
                        "Добавить поле"
                    ], id='add-field-btn', color="secondary", outline=True, size="sm", className="mt-2")
                ])
            ], className="mb-4"),
            
            # Панель предпросмотра
            html.Div(id='markup-preview-panel', className="mb-4"),
            
            # Панель действий
            dbc.Card([
                dbc.CardHeader("Шаг 4: Сохранение конфигурации", className="fw-bold"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Button([
                                html.I(className="fas fa-eye me-2"),
                                "Предпросмотр"
                            ], id='preview-config-btn', color="info", className="me-2"),
                            
                            dbc.Button([
                                html.I(className="fas fa-save me-2"),
                                "Сохранить конфигурацию"
                            ], id='save-config-btn', color="success", className="me-2"),
                            
                            dbc.Button([
                                html.I(className="fas fa-download me-2"),
                                "Экспортировать JSON"
                            ], id='export-config-btn', color="primary")
                        ])
                    ])
                ])
            ]),
            
            # Скрытые хранилища
            dcc.Store(id='markup-image-store'),
            dcc.Store(id='markup-boxes-store', data={}),
            dcc.Store(id='markup-fields-store', data=[]),
            
            # Модальное окно для экспорта
            dbc.Modal([
                dbc.ModalHeader("Экспорт конфигурации"),
                dbc.ModalBody([
                    html.Pre(id='config-json-display', style={'whiteSpace': 'pre-wrap'})
                ]),
                dbc.ModalFooter([
                    dbc.Button("Скопировать", id='copy-json-btn', color="primary"),
                    dbc.Button("Закрыть", id='close-export-modal', color="secondary")
                ])
            ], id='export-modal', size="lg")
        ])
    
    def create_field_editor(self, field_name: str, field_display: str, 
                           box: Optional[Tuple] = None, color: str = '#000000') -> dbc.Card:
        """
        Создание редактора для одного поля с визуальными элементами
        """
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
                            html.Strong(field_display, className="align-middle")
                        ])
                    ], width=3),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("X1", style={'fontSize': '0.8rem'}),
                            dbc.Input(
                                id={'type': 'box-x1', 'field': field_name},
                                type='number',
                                value=box[0] if box else 0,
                                size='sm',
                                style={'width': '80px'}
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("Y1", style={'fontSize': '0.8rem'}),
                            dbc.Input(
                                id={'type': 'box-y1', 'field': field_name},
                                type='number',
                                value=box[1] if box else 0,
                                size='sm',
                                style={'width': '80px'}
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("X2", style={'fontSize': '0.8rem'}),
                            dbc.Input(
                                id={'type': 'box-x2', 'field': field_name},
                                type='number',
                                value=box[2] if box else 100,
                                size='sm',
                                style={'width': '80px'}
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.InputGroupText("Y2", style={'fontSize': '0.8rem'}),
                            dbc.Input(
                                id={'type': 'box-y2', 'field': field_name},
                                type='number',
                                value=box[3] if box else 100,
                                size='sm',
                                style={'width': '80px'}
                            )
                        ], size='sm')
                    ], width=2),
                    
                    dbc.Col([
                        dbc.Button(
                            html.I(className="fas fa-trash"),
                            id={'type': 'delete-field', 'field': field_name},
                            color="danger",
                            size="sm",
                            outline=True
                        )
                    ], width=1)
                ], className="align-items-center")
            ])
        ], className="mb-2")
    
    def draw_boxes_on_image(self, img: Image.Image, boxes: Dict[str, Tuple]) -> Image.Image:
        """
        Отрисовка рамок полей на изображении
        """
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
            
            # Рисуем рамку
            draw.rectangle(box, outline=color, width=3)
            
            # Рисуем подпись
            field_display = next(
                (f['display_name'] for f in self.default_fields if f['name'] == field_name),
                field_name
            )
            
            text_x, text_y = box[0], max(0, box[1] - 25)
            
            # Фон для текста
            text_bbox = draw.textbbox((text_x, text_y), field_display, font=font)
            draw.rectangle(text_bbox, fill=color)
            
            # Текст
            draw.text((text_x, text_y), field_display, fill='white', font=font)
        
        return img_with_boxes
    
    def export_to_config_format(self, config_data: Dict) -> str:
        """
        Экспорт в формат конфигурации для config.py
        """
        config_name = config_data.get('name', 'CustomConfig')
        org = config_data.get('organization', 'CUSTOM')
        doc_type = config_data.get('document_type', 'custom')
        fields = config_data.get('fields', [])
        
        # Генерируем Python код
        code = f'''
def create_{org.lower()}_{doc_type}_config() -> DocumentConfig:
    """
    {config_name}
    Автоматически сгенерировано инструментом разметки
    Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    return DocumentConfig(
        name="{config_name}",
        organization="{org}",
        document_type="{doc_type}",
        config_id="{org}_{doc_type.upper()}",
        description="Конфигурация создана через инструмент разметки",
        fields=[
'''
        
        for field in fields:
            code += f'''            {{
                'name': '{field['name']}',
                'display_name': '{field['display_name']}',
                'box': {field['box']},
                'required': True
            }},
'''
        
        code += '''        ],
        patterns={
            'fullname': CommonParsers.parse_fullname_simple,
            'seriesandnumber': CommonParsers.parse_series_number,
            'registrationnumber': lambda x: (x.strip(), False),
            'issuedate': CommonParsers.parse_date_standard
        },
        ocr_params={
            'scale_factor': 3,
            'contrast_boost': 1.5,
            'sharpness_boost': 1.2
        }
    )
'''
        
        return code


def setup_markup_callbacks(app, markup_tool: MarkupTool):
    """
    Настройка всех callbacks для инструмента разметки
    """
    
    # Callback 1: Загрузка изображения
    @app.callback(
        [Output('markup-image-panel', 'children'),
         Output('markup-image-store', 'data')],
        [Input('markup-upload', 'contents')],
        [State('markup-upload', 'filename')]
    )
    def load_markup_image(contents, filename):
        if not contents:
            return html.P("", className="text-muted"), None
        
        try:
            from core.image_processor import AdvancedImageProcessor
            
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            
            processor = AdvancedImageProcessor(max_dimension=1200)
            images = processor.convert_pdf_from_bytes(decoded)
            
            if not images:
                return html.P("Ошибка загрузки PDF", className="text-danger"), None
            
            img = images[0]
            
            # Конвертируем в base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Создаем панель с изображением
            panel = dbc.Card([
                dbc.CardHeader(f"Образец: {filename} (размер: {img.size[0]}×{img.size[1]}px)"),
                dbc.CardBody([
                    html.Img(
                        id='markup-main-image',
                        src=f"data:image/png;base64,{img_b64}",
                        style={
                            'width': '100%',
                            'height': 'auto',
                            'border': '2px solid #007bff',
                            'cursor': 'crosshair'
                        }
                    ),
                    html.Small(
                        "Используйте инструменты ниже для разметки полей. "
                        "Координаты вводятся вручную (планируется добавление визуального выделения).",
                        className="text-muted d-block mt-2"
                    )
                ])
            ])
            
            return panel, img_b64
            
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            return html.P(f"Ошибка: {str(e)}", className="text-danger"), None
    
    # Callback 2: Инициализация полей
    @app.callback(
        [Output('markup-fields-list', 'children'),
         Output('markup-fields-store', 'data')],
        [Input('markup-base-config', 'value')],
        [State('markup-fields-store', 'data')]
    )
    def initialize_fields(base_config, current_fields):
        if base_config == 'empty':
            # Пустая конфигурация - используем стандартные поля
            fields = []
            for field_def in markup_tool.default_fields:
                fields.append({
                    'name': field_def['name'],
                    'display_name': field_def['display_name'],
                    'box': None
                })
        else:
            # Загружаем из базовой конфигурации
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
            except:
                fields = []
        
        # Создаем редакторы полей
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
    
    # Callback 3: Предпросмотр конфигурации
    @app.callback(
        Output('markup-preview-panel', 'children'),
        [Input('preview-config-btn', 'n_clicks')],
        [State('markup-image-store', 'data'),
         State({'type': 'box-x1', 'field': ALL}, 'value'),
         State({'type': 'box-y1', 'field': ALL}, 'value'),
         State({'type': 'box-x2', 'field': ALL}, 'value'),
         State({'type': 'box-y2', 'field': ALL}, 'value'),
         State({'type': 'box-x1', 'field': ALL}, 'id'),
         State('markup-fields-store', 'data')]
    )
    def preview_configuration(n_clicks, img_b64, x1_values, y1_values, x2_values, y2_values, field_ids, fields):
        if not n_clicks or not img_b64:
            return html.Div()
        
        try:
            # Восстанавливаем изображение
            img_data = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_data))
            
            # Собираем boxes
            boxes = {}
            for i, field_id in enumerate(field_ids):
                field_name = field_id['field']
                if x1_values[i] is not None and y1_values[i] is not None and \
                   x2_values[i] is not None and y2_values[i] is not None:
                    boxes[field_name] = (
                        int(x1_values[i]),
                        int(y1_values[i]),
                        int(x2_values[i]),
                        int(y2_values[i])
                    )
            
            # Рисуем рамки
            img_with_boxes = markup_tool.draw_boxes_on_image(img, boxes)
            
            # Конвертируем обратно
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
    
    # Callback 4: Экспорт конфигурации
    @app.callback(
        [Output('export-modal', 'is_open'),
         Output('config-json-display', 'children')],
        [Input('export-config-btn', 'n_clicks'),
         Input('close-export-modal', 'n_clicks')],
        [State('markup-config-name', 'value'),
         State('markup-org-name', 'value'),
         State('markup-doc-type', 'value'),
         State({'type': 'box-x1', 'field': ALL}, 'value'),
         State({'type': 'box-y1', 'field': ALL}, 'value'),
         State({'type': 'box-x2', 'field': ALL}, 'value'),
         State({'type': 'box-y2', 'field': ALL}, 'value'),
         State({'type': 'box-x1', 'field': ALL}, 'id'),
         State('markup-fields-store', 'data'),
         State('export-modal', 'is_open')]
    )
    def export_configuration(n_export, n_close, config_name, org_name, doc_type,
                           x1_values, y1_values, x2_values, y2_values, field_ids, fields, is_open):
        ctx = callback_context
        if not ctx.triggered:
            return False, ""
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'close-export-modal':
            return False, ""
        
        if button_id == 'export-config-btn':
            # Собираем данные конфигурации
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
                
                if x1_values[i] is not None and y1_values[i] is not None and \
                   x2_values[i] is not None and y2_values[i] is not None:
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
            
            # Генерируем код Python
            code = markup_tool.export_to_config_format(config_data)
            
            return True, code
        
        return is_open, ""
