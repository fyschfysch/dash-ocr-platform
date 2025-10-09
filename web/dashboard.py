"""
Полнофункциональный Dash Dashboard с инструментом разметки
Финальная версия со всеми возможностями
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

# Внутренние импорты
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.ocr_engine import DocumentProcessor
from core.image_processor import AdvancedImageProcessor, ImageAnalyzer, RegionProcessor
from core.config import get_config, get_available_configs, UncertaintyEngine, get_field_description
from web.markup_tool import MarkupTool, setup_markup_callbacks

logger = logging.getLogger(__name__)


class OCRDashboard:
    """
    Полнофункциональный Dashboard с OCR и инструментом разметки
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Инициализация Dashboard
        """
        # Инициализация процессоров
        self.doc_processor = DocumentProcessor(tesseract_cmd)
        self.image_processor = AdvancedImageProcessor(max_dimension=1200)
        self.image_analyzer = ImageAnalyzer()
        self.region_processor = RegionProcessor()
        self.markup_tool = MarkupTool()
        
        # Создание Dash приложения
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[
                dbc.themes.BOOTSTRAP,
                dbc.icons.FONT_AWESOME
            ],
            title="OCR Платформа",
            suppress_callback_exceptions=True
        )
        
        # Настройка layout
        self.app.layout = self.create_main_layout()
        
        # Регистрация всех callbacks
        self.setup_callbacks()
        setup_markup_callbacks(self.app, self.markup_tool)
        
        logger.info("OCRDashboard полностью инициализирован с инструментом разметки")
    
    def create_main_layout(self) -> html.Div:
        """
        Создание главного layout с тремя вкладками
        """
        return dbc.Container([
            # Заголовок
            dbc.Alert([
                html.H1("OCR Платформа для документов", className="mb-2"),
                html.P("Распознавание, редактирование и создание конфигураций", className="mb-0")
            ], color="primary", className="mb-4"),
            
            # Три вкладки
            dbc.Tabs([
                # Вкладка 1: OCR
                dbc.Tab(
                    label="Распознавание документов",
                    tab_id="ocr-tab",
                    children=self.create_ocr_tab()
                ),
                
                # Вкладка 2: Разметка полей
                dbc.Tab(
                    label="Разметка полей",
                    tab_id="markup-tab",
                    children=self.markup_tool.create_markup_layout()
                ),
                
                # Вкладка 3: Справка
                dbc.Tab(
                    label="Справка",
                    tab_id="help-tab",
                    children=self.create_help_tab()
                )
            ], id="main-tabs", active_tab="ocr-tab", className="mb-4"),
            
            # Скрытые хранилища для OCR
            dcc.Store(id='pdf-data-store'),
            dcc.Store(id='pdf-original-store'),
            dcc.Store(id='ocr-results-store'),
            dcc.Store(id='current-config-store'),
            
        ], fluid=True, className="py-4")
    
    def create_ocr_tab(self) -> html.Div:
        """
        Создание вкладки распознавания
        """
        return html.Div([
            # Панель загрузки
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-cloud-upload-alt me-2"),
                    "Загрузка и настройка"
                ], className="fw-bold"),
                dbc.CardBody([
                    # Область загрузки
                    dcc.Upload(
                        id='upload-document',
                        children=dbc.Alert([
                            html.I(className="fas fa-cloud-upload-alt fa-3x mb-3 text-primary"),
                            html.Br(),
                            html.H5("Перетащите PDF файл сюда"),
                            html.P("или нажмите для выбора", className="text-muted mb-1"),
                            html.Small("Поддерживается: PDF до 50MB")
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
                    
                    # Настройки
                    dbc.Row([
                        dbc.Col([
                            html.Label("Тип документа:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='config-selector',
                                options=self._get_config_options(),
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
            
            # Панель статуса
            html.Div(id="status-panel", className="mb-3"),
            
            # Превью первой страницы
            html.Div(id="pdf-preview-panel", className="mb-4"),
            
            # Результаты OCR
            html.Div(id="ocr-results-panel")
        ])
    
    def create_help_tab(self) -> html.Div:
        """
        Создание справочной вкладки
        """
        return dbc.Row([
            dbc.Col([
                # Поддерживаемые организации
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-building me-2"),
                        "Поддерживаемые организации"
                    ]),
                    dbc.CardBody([
                        html.H5([html.I(className="fas fa-certificate me-2 text-primary"), "1Т"]),
                        html.Ul([
                            html.Li("Удостоверения о повышении квалификации"),
                            html.Li("Дипломы о профессиональной переподготовке")
                        ]),
                        
                        html.H5([html.I(className="fas fa-university me-2 text-info"), "РОСНОУ"], className="mt-3"),
                        html.Ul([
                            html.Li("Удостоверения о повышении квалификации"),
                            html.Li("Дипломы о профессиональной переподготовке")
                        ]),
                        
                        html.H5([html.I(className="fas fa-landmark me-2 text-warning"), "Финуниверситет"], className="mt-3"),
                        html.Ul([
                            html.Li("Удостоверения v1 (ФИО в одну строку)"),
                            html.Li("Удостоверения v2 (ФИО на трёх строках)")
                        ])
                    ])
                ], className="mb-3"),
                
                # Возможности платформы
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-star me-2"),
                        "Возможности платформы"
                    ]),
                    dbc.CardBody([
                        html.Ul([
                            html.Li([html.Strong("Превью документа"), " - первая страница на всю ширину"]),
                            html.Li([html.Strong("Визуализация полей"), " - рамки при выборе типа документа"]),
                            html.Li([html.Strong("Редактирование результатов"), " - исправление распознанных значений"]),
                            html.Li([html.Strong("Миниатюры полей"), " - превью вырезанных областей"]),
                            html.Li([html.Strong("Система неуверенности"), " - цветовая индикация проблемных полей"]),
                            html.Li([html.Strong("Экспорт в CSV"), " - сохранение результатов"]),
                            html.Li([html.Strong("Инструмент разметки"), " - создание новых конфигураций"])
                        ])
                    ])
                ])
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
                            html.Li([html.I(className="fas fa-user me-2 text-primary"), "ФИО (в именительном падеже)"]),
                            html.Li([html.I(className="fas fa-id-card me-2 text-info"), "Серия и номер документа"]),
                            html.Li([html.I(className="fas fa-hashtag me-2 text-success"), "Регистрационный номер"]),
                            html.Li([html.I(className="fas fa-calendar me-2 text-warning"), "Дата выдачи (ISO формат)"])
                        ])
                    ])
                ], className="mb-3"),
                
                # Инструкции
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-book me-2"),
                        "Инструкции"
                    ]),
                    dbc.CardBody([
                        html.H6("Распознавание документов:"),
                        html.Ol([
                            html.Li("Загрузите PDF файл"),
                            html.Li("Выберите тип документа из списка"),
                            html.Li("При необходимости укажите поворот"),
                            html.Li("Нажмите 'Запустить OCR'"),
                            html.Li("Отредактируйте поля при необходимости"),
                            html.Li("Скачайте результаты в CSV")
                        ], className="small"),
                        
                        html.H6("Создание новой конфигурации:", className="mt-3"),
                        html.Ol([
                            html.Li("Перейдите на вкладку 'Разметка полей'"),
                            html.Li("Укажите название и организацию"),
                            html.Li("Загрузите образец документа"),
                            html.Li("Введите координаты полей"),
                            html.Li("Используйте предпросмотр"),
                            html.Li("Экспортируйте конфигурацию в JSON")
                        ], className="small")
                    ])
                ]),
                
                # Технические требования
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-cog me-2"),
                        "Технические требования"
                    ]),
                    dbc.CardBody([
                        html.Ul([
                            html.Li("Python 3.8+"),
                            html.Li("Tesseract OCR 4.0+"),
                            html.Li("Браузер с поддержкой HTML5"),
                            html.Li("Рекомендуется: PDF 300 DPI")
                        ], className="small mb-0")
                    ])
                ], className="mt-3")
            ], width=6)
        ])
    
    def _get_config_options(self) -> List[Dict]:
        """Получение опций конфигураций"""
        configs = get_available_configs()
        return [{'label': f"{c['organization']} - {c['name']}", 'value': c['id']} for c in configs]
    
    def setup_callbacks(self):
        """
        Настройка всех callbacks для OCR вкладки
        """
        
        # Callback 1: Загрузка PDF с масштабированием
        @self.app.callback(
            [Output('pdf-data-store', 'data'),
             Output('pdf-original-store', 'data'),
             Output('pdf-preview-panel', 'children'),
             Output('run-ocr-btn', 'disabled'),
             Output('status-panel', 'children')],
            [Input('upload-document', 'contents')],
            [State('upload-document', 'filename')]
        )
        def handle_upload(contents, filename):
            if not contents:
                return None, None, None, True, ""
            
            try:
                content_type, content_string = contents.split(',')
                decoded = base64.b64decode(content_string)
                
                images = self.image_processor.convert_pdf_from_bytes(decoded)
                
                if not images:
                    error = dbc.Alert("Ошибка обработки PDF", color="danger")
                    return None, None, None, True, error
                
                images_original_b64 = []
                images_scaled_b64 = []
                
                for img in images:
                    buffer_orig = io.BytesIO()
                    img.save(buffer_orig, format='PNG')
                    img_orig_b64 = base64.b64encode(buffer_orig.getvalue()).decode()
                    images_original_b64.append(img_orig_b64)
                    
                    img_scaled = self.image_processor.resize_image(img)
                    buffer_scaled = io.BytesIO()
                    img_scaled.save(buffer_scaled, format='PNG')
                    img_scaled_b64 = base64.b64encode(buffer_scaled.getvalue()).decode()
                    images_scaled_b64.append(img_scaled_b64)
                    
                    logger.info(f"Изображение: {img.size} -> {img_scaled.size}")
                
                preview = dbc.Card([
                    dbc.CardHeader(f"{filename} - {len(images)} стр."),
                    dbc.CardBody([
                        html.Img(
                            src=f"data:image/png;base64,{images_scaled_b64[0]}",
                            style={'width': '100%', 'height': 'auto', 'objectFit': 'contain'},
                            className="border"
                        ),
                        html.P(
                            f"Размер: {images[0].size} -> {Image.open(io.BytesIO(base64.b64decode(images_scaled_b64[0]))).size}",
                            className="text-muted small mt-2"
                        )
                    ])
                ])
                
                status = dbc.Alert(
                    f"Загружен: {filename} ({len(images)} стр.). Выберите тип документа.",
                    color="success"
                )
                
                return images_scaled_b64, images_original_b64, preview, False, status
                
            except Exception as e:
                logger.error(f"Ошибка загрузки: {e}")
                error = dbc.Alert(f"Ошибка: {str(e)}", color="danger")
                return None, None, None, True, error
        
        # Callback 2: Отображение полей при выборе конфигурации
        @self.app.callback(
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
                
                img_with_boxes = self.doc_processor.display_image_with_boxes(img, config.fields)
                
                buffer = io.BytesIO()
                img_with_boxes.save(buffer, format='PNG')
                img_with_boxes_b64 = base64.b64encode(buffer.getvalue()).decode()
                
                preview = dbc.Card([
                    dbc.CardHeader([
                        f"{filename} - 1 стр.",
                        dbc.Badge(f"{config.name}", color="info", className="ms-2")
                    ]),
                    dbc.CardBody([
                        html.Img(
                            src=f"data:image/png;base64,{img_with_boxes_b64}",
                            style={'width': '100%', 'height': 'auto', 'objectFit': 'contain'},
                            className="border"
                        ),
                        html.P(
                            f"Размер: {img.size} | Полей: {len(config.fields)}",
                            className="text-muted small mt-2"
                        )
                    ])
                ])
                
                return preview
                
            except Exception as e:
                logger.error(f"Ошибка отображения полей: {e}")
                raise PreventUpdate
        
        # Callback 3: Запуск OCR
        @self.app.callback(
            [Output('ocr-results-panel', 'children'),
             Output('ocr-results-store', 'data'),
             Output('current-config-store', 'data')],
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
                    
                    logger.info(f"OCR страница {page_num + 1}: {img.size}")
                    
                    if rotation:
                        img = self.image_processor.rotate_image(img, rotation)
                    
                    img = self.image_processor.enhance_image_advanced(img)
                    
                    result = self.doc_processor.extract_fields(img, config, uncertainty_engine)
                    result['page'] = page_num + 1
                    result['image_b64'] = img_b64
                    
                    result['field_thumbnails'] = {}
                    for field_config in config.fields:
                        field_name = field_config['name']
                        box = field_config.get('box')
                        
                        if box:
                            thumbnail = self.doc_processor.crop_field_thumbnail(img, box)
                            thumb_buffer = io.BytesIO()
                            thumbnail.save(thumb_buffer, format='PNG')
                            thumb_b64 = base64.b64encode(thumb_buffer.getvalue()).decode()
                            result['field_thumbnails'][field_name] = thumb_b64
                    
                    all_results.append(result)
                
                results_ui = self.create_results_interface(all_results, config)
                
                return results_ui, all_results, config_id
                
            except Exception as e:
                logger.error(f"Ошибка OCR: {e}")
                error = dbc.Alert(f"Ошибка OCR: {str(e)}", color="danger")
                return error, None, None
        
        # Callback 4: Принятие исправлений
        @self.app.callback(
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
    
    def create_results_interface(self, results: List[Dict], config) -> html.Div:
        """Создание интерфейса результатов"""
        components = [
            self.create_summary_panel(results, config),
            html.Hr()
        ]
        
        for page_result in results:
            page_table = self.create_editable_page_table(page_result, config)
            components.append(page_table)
        
        return html.Div(components)
    
    def create_editable_page_table(self, page_result: Dict, config) -> dbc.Card:
        """Создание редактируемой таблицы"""
        page_num = page_result['page']
        uncertainties = page_result.get('uncertainties', [])
        uncertain_fields = {u['field'] for u in uncertainties}
        field_thumbnails = page_result.get('field_thumbnails', {})
        
        table_rows = []
        
        for field_config in config.fields:
            field_name = field_config['name']
            field_display = get_field_description(field_name)
            
            if field_name == 'seriesandnumber':
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
                        style={'maxWidth': '120px', 'maxHeight': '80px', 'objectFit': 'contain'},
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
    
    def create_summary_panel(self, results: List[Dict], config) -> dbc.Card:
        """Создание сводной панели"""
        total_pages = len(results)
        total_uncertainties = sum(len(r.get('uncertainties', [])) for r in results)
        
        export_data = []
        for result in results:
            export_data.append({
                'Страница': result['page'],
                'ФИО': result.get('fullname', ''),
                'Серия': result.get('series', ''),
                'Номер': result.get('number', ''),
                'Рег.номер': result.get('registrationnumber', ''),
                'Дата': result.get('issuedate', '')
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
    
    def run_server(self, debug: bool = True, host: str = '127.0.0.1', port: int = 8050):
        """Запуск веб-сервера"""
        logger.info(f"Запуск Dashboard на http://{host}:{port}")
        try:
            self.app.run(debug=debug, host=host, port=port)
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")
            self.app.server.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    dashboard = OCRDashboard()
    dashboard.run_server(debug=True)
