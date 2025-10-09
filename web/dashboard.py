"""
Полнофункциональный Dash Dashboard для OCR платформы
С редактируемыми полями, миниатюрами и системой неуверенности
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
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging

# Внутренние импорты
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.ocr_engine import DocumentProcessor
from core.image_processor import AdvancedImageProcessor, ImageAnalyzer, RegionProcessor
from core.config import get_config, get_available_configs, UncertaintyEngine, get_field_description

logger = logging.getLogger(__name__)


class OCRDashboard:
    """
    Полнофункциональный Dashboard для OCR с редактируемыми полями
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Инициализация Dashboard
        
        Args:
            tesseract_cmd: Путь к Tesseract
        """
        # Инициализация процессоров
        self.doc_processor = DocumentProcessor(tesseract_cmd)
        self.image_processor = AdvancedImageProcessor()
        self.image_analyzer = ImageAnalyzer()
        self.region_processor = RegionProcessor()
        
        # Создание Dash приложения
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[
                dbc.themes.BOOTSTRAP,
                dbc.icons.FONT_AWESOME,
                "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
            ],
            title="OCR Платформа для документов",
            suppress_callback_exceptions=True
        )
        
        # Настройка layout
        self.app.layout = self.create_main_layout()
        
        # Регистрация callbacks
        self.setup_callbacks()
        
        logger.info("OCRDashboard инициализирован")
    
    def create_main_layout(self) -> html.Div:
        """
        Создание главного layout приложения
        """
        return dbc.Container([
            # Заголовок
            dbc.Alert([
                html.H1([
                    html.I(className="fas fa-search me-3"),
                    "OCR Платформа для документов"
                ], className="mb-2"),
                html.P(
                    "Система распознавания с интерактивным редактированием полей",
                    className="mb-0"
                )
            ], color="primary", className="mb-4"),
            
            # Табы
            dbc.Tabs([
                dbc.Tab(
                    label=[html.I(className="fas fa-file-pdf me-2"), "Распознавание"],
                    tab_id="ocr-tab",
                    children=self.create_ocr_tab()
                ),
                dbc.Tab(
                    label=[html.I(className="fas fa-info-circle me-2"), "Справка"],
                    tab_id="help-tab",
                    children=self.create_help_tab()
                )
            ], id="main-tabs", active_tab="ocr-tab", className="mb-4"),
            
            # Скрытые хранилища
            dcc.Store(id='pdf-data-store'),
            dcc.Store(id='ocr-results-store'),
            dcc.Store(id='field-corrections-store', data={}),
            dcc.Store(id='current-config-store'),
            
        ], fluid=True, className="py-4")
    
    def create_ocr_tab(self) -> html.Div:
        """
        Создание вкладки OCR с полным функционалом
        """
        return html.Div([
            # Панель загрузки
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-cloud-upload-alt me-2"),
                    "Загрузка и настройка"
                ], className="fw-bold"),
                dbc.CardBody([
                    dbc.Row([
                        # Загрузка файла
                        dbc.Col([
                            dcc.Upload(
                                id='upload-document',
                                children=dbc.Alert([
                                    html.I(className="fas fa-cloud-upload-alt fa-3x mb-3 text-primary"),
                                    html.Br(),
                                    html.H5("Перетащите PDF файл сюда"),
                                    html.P("или нажмите для выбора", className="text-muted mb-1"),
                                    html.Small("Поддерживается: PDF до 50MB")
                                ], color="light", className="text-center py-4 mb-0"),
                                style={
                                    'borderWidth': '2px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '10px',
                                    'cursor': 'pointer'
                                },
                                multiple=False,
                                accept='.pdf'
                            )
                        ], width=12, className="mb-3"),
                    ]),
                    
                    html.Hr(),
                    
                    # Настройки
                    dbc.Row([
                        dbc.Col([
                            html.Label("Тип документа:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='config-selector',
                                options=self._get_config_options(),
                                placeholder="Выберите тип документа",
                                className="mb-2"
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
                                value=0,
                                className="mb-2"
                            ),
                        ], width=3),
                        
                        dbc.Col([
                            html.Label(html.Br()),
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
            
            # Превью первой страницы (на всю ширину)
            html.Div(id="pdf-preview-panel", className="mb-4"),
            
            # Результаты OCR с редактируемыми полями
            html.Div(id="ocr-results-panel")
        ])
    
    def create_help_tab(self) -> html.Div:
        """
        Создание справочной вкладки
        """
        return dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📋 Поддерживаемые организации"),
                    dbc.CardBody([
                        html.H5("1Т", className="text-primary"),
                        html.Ul([
                            html.Li("Удостоверения о повышении квалификации"),
                            html.Li("Дипломы о профессиональной переподготовке")
                        ]),
                        
                        html.H5("РОСНОУ", className="text-info mt-3"),
                        html.Ul([
                            html.Li("Удостоверения о повышении квалификации"),
                            html.Li("Дипломы о профессиональной переподготовке")
                        ]),
                        
                        html.H5("Финансовый университет", className="text-warning mt-3"),
                        html.Ul([
                            html.Li("Удостоверения (вариант 1) - ФИО в одну строку"),
                            html.Li("Удостоверения (вариант 2) - ФИО на трёх строках")
                        ])
                    ])
                ])
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("🔧 Извлекаемые поля"),
                    dbc.CardBody([
                        html.Ul([
                            html.Li([html.Strong("ФИО"), " (в именительном падеже)"]),
                            html.Li([html.Strong("Серия и номер"), " документа"]),
                            html.Li([html.Strong("Регистрационный номер")]),
                            html.Li([html.Strong("Дата выдачи"), " (ISO формат)"])
                        ])
                    ])
                ], className="mb-3"),
                
                dbc.Card([
                    dbc.CardHeader("💡 Советы по использованию"),
                    dbc.CardBody([
                        html.Ul([
                            html.Li("Загружайте PDF высокого качества"),
                            html.Li("Выбирайте правильный тип документа"),
                            html.Li("Используйте поворот при необходимости"),
                            html.Li([
                                html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                                "Поля с желтой подсветкой требуют проверки"
                            ])
                        ])
                    ])
                ])
            ], width=6)
        ])
    
    def _get_config_options(self) -> List[Dict]:
        """Получение опций для выбора конфигурации"""
        configs = get_available_configs()
        return [
            {
                'label': f"{conf['organization']} - {conf['name']}",
                'value': conf['id']
            }
            for conf in configs
        ]
    
    def setup_callbacks(self):
        """
        Настройка всех callbacks
        """
        
        # Callback 1: Загрузка PDF
        @self.app.callback(
            [Output('pdf-data-store', 'data'),
             Output('pdf-preview-panel', 'children'),
             Output('run-ocr-btn', 'disabled'),
             Output('status-panel', 'children')],
            [Input('upload-document', 'contents')],
            [State('upload-document', 'filename')]
        )
        def handle_upload(contents, filename):
            """Обработка загрузки PDF с превью только первой страницы"""
            if not contents:
                return None, None, True, ""
            
            try:
                # Декодируем
                content_type, content_string = contents.split(',')
                decoded = base64.b64decode(content_string)
                
                # Конвертируем PDF
                images = self.image_processor.convert_pdf_from_bytes(decoded)
                
                if not images:
                    error = dbc.Alert("Ошибка обработки PDF", color="danger")
                    return None, None, True, error
                
                # Сохраняем все страницы
                images_b64 = []
                for img in images:
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    img_b64 = base64.b64encode(buffer.getvalue()).decode()
                    images_b64.append(img_b64)
                
                # Превью ТОЛЬКО первой страницы на всю ширину
                preview = dbc.Card([
                    dbc.CardHeader(f"📄 {filename} - {len(images)} страниц"),
                    dbc.CardBody([
                        html.Div([
                            html.Img(
                                src=f"data:image/png;base64,{images_b64[0]}",
                                style={
                                    'width': '100%',
                                    'height': 'auto',
                                    'object-fit': 'contain',
                                    'max-height': '70vh'
                                },
                                className="border shadow-sm"
                            )
                        ], className="text-center")
                    ])
                ])
                
                status = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"Загружен: {filename} ({len(images)} стр.). Выберите тип документа."
                ], color="success")
                
                return images_b64, preview, False, status
                
            except Exception as e:
                logger.error(f"Ошибка загрузки: {e}")
                error = dbc.Alert(f"Ошибка: {str(e)}", color="danger")
                return None, None, True, error
        
        # Callback 2: Запуск OCR
        @self.app.callback(
            [Output('ocr-results-panel', 'children'),
             Output('ocr-results-store', 'data'),
             Output('current-config-store', 'data')],
            [Input('run-ocr-btn', 'n_clicks')],
            [State('pdf-data-store', 'data'),
             State('config-selector', 'value'),
             State('rotation-selector', 'value')]
        )
        def run_ocr_processing(n_clicks, pdf_data, config_id, rotation):
            """Полноценная OCR обработка"""
            if not n_clicks or not pdf_data or not config_id:
                raise PreventUpdate
            
            try:
                # Загружаем конфигурацию
                config = get_config(config_id)
                uncertainty_engine = UncertaintyEngine(config.organization)
                
                # Обрабатываем все страницы
                all_results = []
                
                for page_num, img_b64 in enumerate(pdf_data):
                    # Восстанавливаем изображение
                    img_data = base64.b64decode(img_b64)
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Поворот
                    if rotation:
                        img = self.image_processor.rotate_image(img, rotation)
                    
                    # Масштабирование и улучшение
                    img = self.image_processor.resize_image(img)
                    img = self.image_processor.enhance_image_advanced(img)
                    
                    # OCR через полноценный движок
                    result = self.doc_processor.extract_fields(img, config, uncertainty_engine)
                    result['page'] = page_num + 1
                    result['image_b64'] = img_b64
                    
                    # Создаем миниатюры полей
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
                
                # Создаем интерфейс результатов
                results_ui = self.create_results_interface(all_results, config)
                
                return results_ui, all_results, config_id
                
            except Exception as e:
                logger.error(f"Ошибка OCR: {e}")
                error = dbc.Alert(f"Ошибка OCR: {str(e)}", color="danger")
                return error, None, None
        
        # Callback 3: Принятие исправлений
        @self.app.callback(
            [Output('ocr-results-store', 'data', allow_duplicate=True),
             Output({'type': 'field-status', 'page': MATCH, 'field': MATCH}, 'children')],
            [Input({'type': 'accept-btn', 'page': MATCH, 'field': MATCH}, 'n_clicks')],
            [State({'type': 'field-input', 'page': MATCH, 'field': MATCH}, 'value'),
             State({'type': 'field-input', 'page': MATCH, 'field': MATCH}, 'id'),
             State('ocr-results-store', 'data')],
            prevent_initial_call=True
        )
        def accept_correction(n_clicks, new_value, field_id, results_data):
            """Принятие исправления поля"""
            if not n_clicks or new_value is None or not results_data:
                raise PreventUpdate
            
            page_num = field_id['page']
            field_name = field_id['field']
            
            # Обновляем значение
            page_idx = page_num - 1
            if page_idx < len(results_data):
                results_data[page_idx][field_name] = new_value
                
                # Убираем из неуверенных
                uncertainties = results_data[page_idx].get('uncertainties', [])
                results_data[page_idx]['uncertainties'] = [
                    u for u in uncertainties if u['field'] != field_name
                ]
                
                logger.info(f"Принято исправление: страница {page_num}, поле {field_name}")
            
            status = html.Span([
                html.I(className="fas fa-check-circle text-success me-1"),
                "Принято"
            ])
            
            return results_data, status
        
        # Callback 4: Экспорт CSV
        @self.app.callback(
            Output('download-csv', 'data'),
            [Input('export-csv-btn', 'n_clicks')],
            [State('ocr-results-store', 'data')],
            prevent_initial_call=True
        )
        def export_csv(n_clicks, results_data):
            """Экспорт результатов в CSV"""
            if not n_clicks or not results_data:
                raise PreventUpdate
            
            # Создаем DataFrame
            export_data = []
            for result in results_data:
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
            
            return dcc.send_data_frame(
                df.to_csv,
                f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                index=False
            )
    
    def create_results_interface(self, results: List[Dict], config) -> html.Div:
        """
        Создание интерфейса результатов с редактируемыми полями
        """
        components = [
            self.create_summary_panel(results, config),
            html.Hr()
        ]
        
        # Для каждой страницы создаем редактируемую таблицу
        for page_result in results:
            page_table = self.create_editable_page_table(page_result, config)
            components.append(page_table)
        
        return html.Div(components)
    
    def create_editable_page_table(self, page_result: Dict, config) -> dbc.Card:
        """
        Создание редактируемой таблицы для страницы с миниатюрами
        """
        page_num = page_result['page']
        uncertainties = page_result.get('uncertainties', [])
        uncertain_fields = {u['field'] for u in uncertainties}
        field_thumbnails = page_result.get('field_thumbnails', {})
        
        # Создаем строки таблицы
        table_rows = []
        
        for field_config in config.fields:
            field_name = field_config['name']
            field_display = get_field_description(field_name)
            
            # Получаем значение поля
            if field_name == 'seriesandnumber':
                value = f"{page_result.get('series', '')} {page_result.get('number', '')}".strip()
            else:
                value = page_result.get(field_name, '')
            
            # Миниатюра поля
            thumb_b64 = field_thumbnails.get(field_name, '')
            
            # Определяем стиль (неуверенные поля выделяем)
            is_uncertain = field_name in uncertain_fields
            row_class = "table-warning" if is_uncertain else ""
            
            # Создаем строку таблицы
            row = html.Tr([
                # Название поля
                html.Td([
                    html.Strong(field_display),
                    html.I(className="fas fa-exclamation-triangle ms-2 text-warning")
                    if is_uncertain else ""
                ], style={'width': '20%'}),
                
                # Миниатюра
                html.Td([
                    html.Img(
                        src=f"data:image/png;base64,{thumb_b64}",
                        style={'max-width': '120px', 'max-height': '80px'},
                        className="border"
                    ) if thumb_b64 else html.Span("—", className="text-muted")
                ], style={'width': '15%', 'text-align': 'center'}),
                
                # Редактируемое поле
                html.Td([
                    dcc.Input(
                        id={'type': 'field-input', 'page': page_num, 'field': field_name},
                        value=str(value),
                        debounce=True,
                        style={
                            'width': '100%',
                            'background-color': '#fff3cd' if is_uncertain else '#fff'
                        }
                    )
                ], style={'width': '45%'}),
                
                # Кнопка и статус
                html.Td([
                    dbc.Button(
                        "✓ Принять",
                        id={'type': 'accept-btn', 'page': page_num, 'field': field_name},
                        color="success",
                        size="sm",
                        className="me-2"
                    ),
                    html.Span(
                        id={'type': 'field-status', 'page': page_num, 'field': field_name},
                        className="text-muted small"
                    )
                ], style={'width': '20%'})
                
            ], className=row_class)
            
            table_rows.append(row)
        
        return dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-edit me-2"),
                f"Страница {page_num} - Редактирование полей"
            ], className="fw-bold"),
            dbc.CardBody([
                dbc.Table([
                    html.Thead([
                        html.Tr([
                            html.Th("Поле"),
                            html.Th("Превью"),
                            html.Th("Значение"),
                            html.Th("Действие")
                        ])
                    ]),
                    html.Tbody(table_rows)
                ], bordered=True, hover=True, striped=True, responsive=True)
            ])
        ], className="mb-4")
    
    def create_summary_panel(self, results: List[Dict], config) -> dbc.Card:
        """
        Создание сводной панели результатов
        """
        total_pages = len(results)
        total_uncertainties = sum(len(r.get('uncertainties', [])) for r in results)
        
        # DataFrame для экспорта
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
        
        # CSV для скачивания
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_b64 = base64.b64encode(csv_buffer.getvalue().encode()).decode()
        
        return dbc.Card([
            dbc.CardHeader("📊 Сводка результатов"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H5(f"Страниц: {total_pages}"),
                        html.P(f"Конфигурация: {config.name}"),
                        html.P([
                            html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                            f"Требуют проверки: {total_uncertainties}"
                        ] if total_uncertainties > 0 else "✓ Все поля распознаны уверенно")
                    ], width=8),
                    
                    dbc.Col([
                        html.A(
                            dbc.Button([
                                html.I(className="fas fa-download me-2"),
                                "Скачать CSV"
                            ], color="success", size="lg", className="w-100"),
                            href=f"data:text/csv;charset=utf-8;base64,{csv_b64}",
                            download=f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        ),
                        dcc.Download(id='download-csv')
                    ], width=4)
                ])
            ])
        ], className="mb-4")
    
    def run_server(self, debug: bool = True, host: str = '127.0.0.1', port: int = 8050):
        """
        Запуск веб-сервера
        """
        logger.info(f"🚀 Запуск Dashboard на http://{host}:{port}")
        try:
            self.app.run(debug=debug, host=host, port=port)
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")
            self.app.server.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    dashboard = OCRDashboard()
    dashboard.run_server(debug=True)
