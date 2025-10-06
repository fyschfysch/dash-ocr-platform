"""
Интерактивный инструмент для разметки полей документов
Использует Plotly для создания canvas с возможностью выделения областей мышью
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from PIL import Image
import numpy as np
import json
from typing import Dict, List, Tuple, Optional, Any
import io
import base64


class MarkupTool:
    """
    Инструмент для интерактивной разметки полей на изображении документа
    """
    
    def __init__(self):
        self.current_image = None
        self.image_width = 0
        self.image_height = 0
        self.fields = []
        self.current_field_type = None
        self.selection_mode = False
        
        # Цвета для разных типов полей
        self.field_colors = {
            'fullname': '#FF6B6B',
            'seriesandnumber': '#4ECDC4',
            'registrationnumber': '#45B7D1',
            'issuedate': '#96CEB4',
            'series': '#FFEAA7',
            'number': '#DDA0DD'
        }
    
    def create_markup_layout(self) -> html.Div:
        """
        Создает layout для инструмента разметки
        """
        return html.Div([
            # Заголовок
            html.H3("🎯 Интерактивная разметка полей документа", 
                   className="text-center mb-4"),
            
            # Панель инструментов
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # Выбор типа поля
                        dbc.Col([
                            html.Label("Тип поля для разметки:", className="fw-bold"),
                            dcc.Dropdown(
                                id='field-type-selector',
                                options=[
                                    {'label': 'ФИО', 'value': 'fullname'},
                                    {'label': 'Серия и номер', 'value': 'seriesandnumber'},
                                    {'label': 'Рег. номер', 'value': 'registrationnumber'},
                                    {'label': 'Дата выдачи', 'value': 'issuedate'}
                                ],
                                placeholder="Выберите тип поля",
                                className="mb-2"
                            )
                        ], width=3),
                        
                        # Кнопки управления
                        dbc.Col([
                            html.Label("Управление:", className="fw-bold"),
                            html.Br(),
                            dbc.ButtonGroup([
                                dbc.Button("🎯 Начать разметку", id="start-markup-btn", 
                                          color="success", size="sm", disabled=True),
                                dbc.Button("🗑️ Очистить поля", id="clear-fields-btn", 
                                          color="warning", size="sm"),
                                dbc.Button("💾 Сохранить конфигурацию", id="save-config-btn", 
                                          color="primary", size="sm")
                            ])
                        ], width=4),
                        
                        # Информация о текущем состоянии
                        dbc.Col([
                            html.Label("Статус:", className="fw-bold"),
                            html.Div(id="markup-status", 
                                   children="Загрузите изображение для начала разметки",
                                   className="small text-muted")
                        ], width=5)
                    ])
                ])
            ], className="mb-4"),
            
            # График с изображением
            html.Div([
                dcc.Graph(
                    id='markup-image',
                    config={
                        'displayModeBar': True,
                        'modeBarButtonsToAdd': ['select2d', 'lasso2d'],
                        'modeBarButtonsToRemove': ['zoom2d', 'pan2d'],
                        'displaylogo': False
                    },
                    style={'height': '70vh'}
                )
            ], className="mb-4"),
            
            # Список размеченных полей
            dbc.Card([
                dbc.CardHeader("📋 Размеченные поля"),
                dbc.CardBody([
                    html.Div(id="fields-list")
                ])
            ], className="mb-4"),
            
            # Экспорт конфигурации
            dbc.Collapse([
                dbc.Card([
                    dbc.CardHeader("💾 Экспорт конфигурации"),
                    dbc.CardBody([
                        html.Label("JSON конфигурация полей:", className="fw-bold"),
                        dcc.Textarea(
                            id="config-export",
                            style={'width': '100%', 'height': 200, 'fontFamily': 'monospace'},
                            readOnly=True
                        ),
                        html.Br(),
                        html.Br(),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Название конфигурации:", className="fw-bold"),
                                dbc.Input(id="config-name", placeholder="Например: MY_ORG_CERTIFICATE")
                            ], width=6),
                            dbc.Col([
                                html.Label("Организация:", className="fw-bold"),
                                dbc.Input(id="config-organization", placeholder="Например: МОЯ_ОРГАНИЗАЦИЯ")
                            ], width=6)
                        ])
                    ])
                ])
            ], id="export-collapse", is_open=False),
            
            # Скрытые div для хранения данных
            html.Div(id="markup-data", style={'display': 'none'}),
            html.Div(id="image-data", style={'display': 'none'})
        ])
    
    def create_empty_figure(self) -> go.Figure:
        """
        Создает пустой график-заглушку
        """
        fig = go.Figure()
        fig.add_annotation(
            text="Загрузите изображение для начала разметки",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            xaxis={'visible': False},
            yaxis={'visible': False},
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    def create_image_figure(self, img: Image.Image, fields: List[Dict] = None) -> go.Figure:
        """
        Создает график с изображением и размеченными полями
        
        Args:
            img: PIL изображение
            fields: Список полей с координатами
            
        Returns:
            Plotly figure
        """
        # Конвертируем PIL в numpy array
        img_array = np.array(img)
        
        # Создаем figure
        fig = go.Figure()
        
        # Добавляем изображение
        fig.add_trace(
            go.Image(z=img_array, name="Документ")
        )
        
        # Добавляем размеченные поля
        if fields:
            for i, field in enumerate(fields):
                if 'box' in field and 'name' in field:
                    x1, y1, x2, y2 = field['box']
                    color = self.field_colors.get(field['name'], '#FF0000')
                    
                    # Добавляем прямоугольник
                    fig.add_shape(
                        type="rect",
                        x0=x1, y0=y1, x1=x2, y1=y2,
                        line=dict(color=color, width=3),
                        fillcolor=color,
                        opacity=0.2,
                        layer="above"
                    )
                    
                    # Добавляем подпись
                    fig.add_annotation(
                        x=x1, y=y1-10,
                        text=field.get('label', field['name']),
                        showarrow=False,
                        font=dict(color=color, size=12),
                        bgcolor="white",
                        bordercolor=color,
                        borderwidth=1
                    )
        
        # Настройка layout
        fig.update_layout(
            title="Кликните и перетащите для выделения области поля",
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                range=[0, img.width]
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                range=[img.height, 0],  # Инвертируем Y для соответствия изображению
                scaleanchor="x",
                scaleratio=1
            ),
            dragmode="select",
            selectdirection="diagonal",
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=0, r=0, t=50, b=0)
        )
        
        return fig
    
    def extract_selection_coordinates(self, selection_data: Dict) -> Optional[Tuple[int, int, int, int]]:
        """
        Извлекает координаты выделенной области
        
        Args:
            selection_data: Данные выделения from Plotly
            
        Returns:
            Tuple координат (x1, y1, x2, y2) или None
        """
        if not selection_data or 'range' not in selection_data:
            return None
        
        try:
            x_range = selection_data['range']['x']
            y_range = selection_data['range']['y']
            
            x1, x2 = min(x_range), max(x_range)
            y1, y2 = min(y_range), max(y_range)
            
            # Округляем координаты
            return (int(x1), int(y1), int(x2), int(y2))
            
        except (KeyError, TypeError, ValueError):
            return None
    
    def validate_selection(self, coordinates: Tuple[int, int, int, int]) -> bool:
        """
        Проверяет корректность выделенной области
        """
        x1, y1, x2, y2 = coordinates
        
        # Минимальный размер области
        min_width, min_height = 20, 10
        
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        
        return width >= min_width and height >= min_height
    
    def create_fields_list_layout(self, fields: List[Dict]) -> html.Div:
        """
        Создает список размеченных полей
        """
        if not fields:
            return html.P("Поля не размечены", className="text-muted")
        
        field_items = []
        for i, field in enumerate(fields):
            color = self.field_colors.get(field['name'], '#FF0000')
            box = field.get('box', [0, 0, 0, 0])
            
            field_items.append(
                dbc.ListGroupItem([
                    dbc.Row([
                        dbc.Col([
                            html.Span(
                                field.get('label', field['name']), 
                                className="fw-bold",
                                style={'color': color}
                            ),
                            html.Small(
                                f" ({field['name']})",
                                className="text-muted"
                            )
                        ], width=6),
                        dbc.Col([
                            html.Small(
                                f"Координаты: ({box[0]}, {box[1]}) - ({box[2]}, {box[3]})",
                                className="text-muted"
                            )
                        ], width=4),
                        dbc.Col([
                            dbc.Button(
                                "🗑️", 
                                id={'type': 'delete-field-btn', 'index': i},
                                color="outline-danger",
                                size="sm"
                            )
                        ], width=2)
                    ])
                ])
            )
        
        return dbc.ListGroup(field_items)
    
    def export_config(self, fields: List[Dict], config_name: str, 
                     organization: str) -> str:
        """
        Экспортирует конфигурацию в JSON формат
        """
        config = {
            'name': config_name or "CUSTOM_CONFIG",
            'organization': organization or "CUSTOM_ORG",
            'document_type': "custom",
            'fields': [
                {
                    'name': field['name'],
                    'box': field['box'],
                    'label': field.get('label', field['name'])
                }
                for field in fields
            ],
            'patterns': {
                # Здесь можно добавить стандартные парсеры
                field['name']: f"parse_{field['name']}"
                for field in fields
            },
            'ocr_params': {
                'scale_factor': 4,
                'contrast_boost': 1.5
            }
        }
        
        return json.dumps(config, ensure_ascii=False, indent=2)
    
    def load_image_from_base64(self, base64_string: str) -> Optional[Image.Image]:
        """
        Загружает изображение из base64 строки
        """
        try:
            # Убираем префикс data:image/...;base64,
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]
            
            # Декодируем
            image_data = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_data))
            
            return image
            
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")
            return None


# Callbacks для интерактивности (будут подключены в основном приложении)
def setup_markup_callbacks(app: dash.Dash, markup_tool: MarkupTool):
    """
    Настройка callbacks для инструмента разметки
    """
    
    @app.callback(
        [Output('start-markup-btn', 'disabled'),
         Output('markup-status', 'children')],
        [Input('field-type-selector', 'value'),
         Input('image-data', 'children')]
    )
    def update_markup_button(field_type, image_data):
        """Активация кнопки начала разметки"""
        if field_type and image_data:
            return False, f"Готов к разметке поля: {field_type}"
        elif image_data:
            return True, "Выберите тип поля для разметки"
        else:
            return True, "Загрузите изображение для начала разметки"
    
    @app.callback(
        Output('markup-image', 'figure'),
        [Input('image-data', 'children'),
         Input('markup-data', 'children')]
    )
    def update_image_figure(image_data, markup_data):
        """Обновление изображения с разметкой"""
        if not image_data:
            return markup_tool.create_empty_figure()
        
        try:
            # Загружаем изображение
            img = markup_tool.load_image_from_base64(image_data)
            if not img:
                return markup_tool.create_empty_figure()
            
            # Загружаем поля разметки
            fields = json.loads(markup_data) if markup_data else []
            
            return markup_tool.create_image_figure(img, fields)
            
        except Exception as e:
            print(f"Ошибка обновления изображения: {e}")
            return markup_tool.create_empty_figure()
    
    @app.callback(
        [Output('markup-data', 'children'),
         Output('fields-list', 'children')],
        [Input('markup-image', 'selectedData'),
         Input('clear-fields-btn', 'n_clicks')],
        [State('field-type-selector', 'value'),
         State('markup-data', 'children')]
    )
    def handle_selection(selected_data, clear_clicks, field_type, current_markup_data):
        """Обработка выделения области на изображении"""
        ctx = callback_context
        
        # Очистка полей
        if ctx.triggered and 'clear-fields-btn' in ctx.triggered[0]['prop_id']:
            return json.dumps([]), markup_tool.create_fields_list_layout([])
        
        # Обработка выделения
        if selected_data and field_type:
            coordinates = markup_tool.extract_selection_coordinates(selected_data)
            
            if coordinates and markup_tool.validate_selection(coordinates):
                # Загружаем текущие поля
                fields = json.loads(current_markup_data) if current_markup_data else []
                
                # Добавляем новое поле
                new_field = {
                    'name': field_type,
                    'box': list(coordinates),
                    'label': {
                        'fullname': 'ФИО',
                        'seriesandnumber': 'Серия и номер',
                        'registrationnumber': 'Рег. номер',
                        'issuedate': 'Дата выдачи'
                    }.get(field_type, field_type)
                }
                
                # Проверяем, не существует ли уже поле такого типа
                fields = [f for f in fields if f['name'] != field_type]
                fields.append(new_field)
                
                fields_list = markup_tool.create_fields_list_layout(fields)
                return json.dumps(fields), fields_list
        
        # Возвращаем текущее состояние
        current_fields = json.loads(current_markup_data) if current_markup_data else []
        fields_list = markup_tool.create_fields_list_layout(current_fields)
        return current_markup_data or json.dumps([]), fields_list
    
    @app.callback(
        [Output('export-collapse', 'is_open'),
         Output('config-export', 'value')],
        [Input('save-config-btn', 'n_clicks')],
        [State('markup-data', 'children'),
         State('config-name', 'value'),
         State('config-organization', 'value')]
    )
    def export_configuration(save_clicks, markup_data, config_name, organization):
        """Экспорт конфигурации"""
        if save_clicks and markup_data:
            fields = json.loads(markup_data)
            if fields:
                config_json = markup_tool.export_config(fields, config_name, organization)
                return True, config_json
        
        return False, ""


# Дополнительные утилиты для интеграции с основным приложением
class MarkupIntegration:
    """
    Утилиты для интеграции инструмента разметки с основным приложением
    """
    
    @staticmethod
    def image_to_base64(img: Image.Image) -> str:
        """
        Конвертирует PIL изображение в base64 строку
        """
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def validate_config_json(config_str: str) -> Tuple[bool, str]:
        """
        Валидирует JSON конфигурацию
        
        Returns:
            Tuple[is_valid, error_message]
        """
        try:
            config = json.loads(config_str)
            
            required_fields = ['name', 'organization', 'fields']
            for field in required_fields:
                if field not in config:
                    return False, f"Отсутствует обязательное поле: {field}"
            
            if not isinstance(config['fields'], list):
                return False, "Поле 'fields' должно быть списком"
            
            for i, field in enumerate(config['fields']):
                if 'name' not in field or 'box' not in field:
                    return False, f"Поле {i+1}: отсутствует 'name' или 'box'"
                
                if not isinstance(field['box'], list) or len(field['box']) != 4:
                    return False, f"Поле {i+1}: 'box' должен содержать 4 координаты"
            
            return True, ""
            
        except json.JSONDecodeError as e:
            return False, f"Ошибка JSON: {str(e)}"
        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}"
