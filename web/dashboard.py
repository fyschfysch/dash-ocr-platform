"""
Рабочая версия OCR Dashboard с минимальной функциональностью
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate

import fitz  # PyMuPDF для PDF
from PIL import Image
import pandas as pd
import io
import base64
import os
from datetime import datetime
import logging

# Минимальные импорты для OCR
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)


class SimpleOCRProcessor:
    """
    Упрощенный OCR процессор для тестирования
    """
    
    def __init__(self, tesseract_cmd=None):
        self.tesseract_cmd = tesseract_cmd
        
        # Попробуем импортировать pytesseract
        try:
            import pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            self.ocr_available = True
            logger.info("✅ Tesseract OCR доступен")
        except ImportError:
            self.ocr_available = False
            logger.warning("⚠️ pytesseract не установлен")
    
    def convert_pdf_to_images(self, pdf_bytes):
        """Конвертация PDF в изображения"""
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            images = []
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                # Конвертируем в изображение с хорошим качеством
                mat = fitz.Matrix(2.0, 2.0)  # Увеличиваем разрешение
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Конвертируем в PIL Image
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
                
                logger.info(f"Страница {page_num + 1}: {img.size}")
            
            pdf_document.close()
            return images
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF: {e}")
            return []
    
    def extract_text_simple(self, img):
        """Простое извлечение текста из изображения"""
        if not self.ocr_available:
            return {
                'fullname': 'OCR недоступен (pytesseract не установлен)',
                'series': 'N/A',
                'number': 'N/A', 
                'registrationnumber': 'N/A',
                'issuedate': 'N/A'
            }
        
        try:
            import pytesseract
            
            # Простое OCR всего изображения
            text = pytesseract.image_to_string(img, lang='rus')
            
            # Простейший парсинг (для демонстрации)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            result = {
                'fullname': lines[0] if len(lines) > 0 else 'Не распознано',
                'series': 'XX',
                'number': '123456',
                'registrationnumber': '000001',
                'issuedate': '2024-01-01',
                'raw_text': text[:200] + '...' if len(text) > 200 else text
            }
            
            logger.info(f"OCR выполнен, найдено {len(lines)} строк")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}")
            return {
                'fullname': f'Ошибка OCR: {str(e)}',
                'series': 'N/A',
                'number': 'N/A',
                'registrationnumber': 'N/A', 
                'issuedate': 'N/A'
            }


class OCRDashboard:
    """
    Рабочая версия OCR Dashboard
    """
    
    def __init__(self, tesseract_cmd=None):
        """Инициализация с минимальными компонентами"""
        
        # Инициализация OCR процессора
        self.ocr_processor = SimpleOCRProcessor(tesseract_cmd)
        
        # Создание Dash приложения
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[
                dbc.themes.BOOTSTRAP,
                dbc.icons.FONT_AWESOME
            ],
            title="OCR Платформа"
        )
        
        # Layout и callbacks
        self.app.layout = self.create_layout()
        self.setup_callbacks()
    
    def create_layout(self):
        """Создание layout с функциональностью"""
        return dbc.Container([
            # Заголовок
            dbc.Alert([
                html.H1([
                    html.I(className="fas fa-search me-3"),
                    "OCR Платформа для документов"
                ]),
                html.P("Система распознавания документов с Tesseract OCR", className="mb-0")
            ], color="primary", className="mb-4"),
            
            # Основная панель загрузки
            dbc.Card([
                dbc.CardHeader("📤 Загрузка и обработка документа"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            # Область загрузки файла
                            dcc.Upload(
                                id='upload-document',
                                children=dbc.Alert([
                                    html.I(className="fas fa-cloud-upload-alt fa-3x mb-3"),
                                    html.Br(),
                                    html.H5("Перетащите PDF файл сюда"),
                                    html.P("или нажмите для выбора файла", className="text-muted"),
                                    html.Small("Поддерживаются: PDF до 50MB")
                                ], color="light", className="text-center py-4"),
                                style={
                                    'borderWidth': '2px',
                                    'borderStyle': 'dashed',
                                    'borderRadius': '10px',
                                    'borderColor': '#007bff',
                                    'cursor': 'pointer'
                                },
                                multiple=False,
                                accept='.pdf'
                            )
                        ], width=8),
                        
                        dbc.Col([
                            # Настройки
                            html.Label("Тип документа:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='config-selector',
                                options=[
                                    {'label': '🏢 1Т - Удостоверение', 'value': '1T_CERTIFICATE'},
                                    {'label': '🏢 1Т - Диплом', 'value': '1T_DIPLOMA'},
                                    {'label': '🏛️ РОСНОУ - Диплом', 'value': 'ROSNOU_DIPLOMA'},
                                    {'label': '🏛️ РОСНОУ - Удостоверение', 'value': 'ROSNOU_CERTIFICATE'},
                                    {'label': '🏦 ФинУнив - Удостоверение', 'value': 'FINUNIV_CERT'}
                                ],
                                placeholder="Выберите тип документа",
                                className="mb-3"
                            ),
                            
                            html.Label("Поворот:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='rotation-selector',
                                options=[
                                    {'label': 'Без поворота', 'value': 0},
                                    {'label': '90°', 'value': 90},
                                    {'label': '180°', 'value': 180},
                                    {'label': '270°', 'value': 270}
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
                                className="w-100"
                            )
                        ], width=4)
                    ])
                ])
            ], className="mb-4"),
            
            # Панель статуса
            html.Div(id="status-panel"),
            
            # Превью PDF
            html.Div(id="pdf-preview-panel", className="mb-4"),
            
            # Результаты OCR
            html.Div(id="ocr-results-panel"),
            
            # Скрытое хранилище данных
            dcc.Store(id='pdf-data-store')
            
        ], fluid=True, className="py-4")
    
    def setup_callbacks(self):
        """Настройка всех callbacks"""
        
        @self.app.callback(
            [Output('pdf-data-store', 'data'),
             Output('pdf-preview-panel', 'children'),
             Output('run-ocr-btn', 'disabled'),
             Output('status-panel', 'children')],
            [Input('upload-document', 'contents')],
            [State('upload-document', 'filename')]
        )
        def handle_upload(contents, filename):
            """Обработка загрузки PDF"""
            if not contents:
                return None, None, True, ""
            
            try:
                # Декодируем файл
                content_type, content_string = contents.split(',')
                decoded = base64.b64decode(content_string)
                
                # Конвертируем PDF в изображения
                images = self.ocr_processor.convert_pdf_to_images(decoded)
                
                if not images:
                    error_status = dbc.Alert([
                        html.I(className="fas fa-exclamation-triangle me-2"),
                        "Ошибка: не удалось обработать PDF файл"
                    ], color="danger")
                    return None, None, True, error_status
                
                # Сохраняем изображения в base64 для хранения
                images_b64 = []
                preview_components = []
                
                for i, img in enumerate(images):
                    # Конвертируем в base64
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    img_b64 = base64.b64encode(buffer.getvalue()).decode()
                    images_b64.append(img_b64)
                    
                    # Создаем превью для первых 3 страниц
                    if i < 3:
                        # Создаем миниатюру
                        thumbnail = img.copy()
                        thumbnail.thumbnail((200, 300), Image.LANCZOS)
                        thumb_buffer = io.BytesIO()
                        thumbnail.save(thumb_buffer, format='PNG')
                        thumb_b64 = base64.b64encode(thumb_buffer.getvalue()).decode()
                        
                        preview_components.append(
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardImg(
                                        src=f"data:image/png;base64,{thumb_b64}",
                                        top=True,
                                        style={'height': '200px', 'object-fit': 'contain'}
                                    ),
                                    dbc.CardBody([
                                        html.H6(f"Страница {i + 1}", className="text-center"),
                                        html.Small(f"{img.width}×{img.height}px", 
                                                 className="text-muted text-center d-block")
                                    ], className="py-2")
                                ])
                            ], width=4, className="mb-3")
                        )
                
                # Превью панель
                preview_panel = dbc.Card([
                    dbc.CardHeader(f"📄 {filename} - {len(images)} страниц"),
                    dbc.CardBody([
                        dbc.Row(preview_components) if preview_components else html.P("Превью недоступно")
                    ])
                ])
                
                # Статус успеха
                success_status = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"PDF загружен успешно! Страниц: {len(images)}. Выберите настройки и запустите OCR."
                ], color="success")
                
                return images_b64, preview_panel, False, success_status
                
            except Exception as e:
                error_status = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Ошибка загрузки: {str(e)}"
                ], color="danger")
                return None, None, True, error_status
        
        @self.app.callback(
            Output('ocr-results-panel', 'children'),
            [Input('run-ocr-btn', 'n_clicks')],
            [State('pdf-data-store', 'data'),
             State('config-selector', 'value'),
             State('rotation-selector', 'value')]
        )
        def run_ocr(n_clicks, pdf_data, config, rotation):
            """Запуск OCR обработки"""
            if not n_clicks or not pdf_data or not config:
                raise PreventUpdate
            
            try:
                # Восстанавливаем изображения из base64
                images = []
                for img_b64 in pdf_data:
                    img_data = base64.b64decode(img_b64)
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Применяем поворот если нужно
                    if rotation == 90:
                        img = img.transpose(Image.ROTATE_90)
                    elif rotation == 180:
                        img = img.transpose(Image.ROTATE_180)
                    elif rotation == 270:
                        img = img.transpose(Image.ROTATE_270)
                    
                    images.append(img)
                
                # Выполняем OCR для каждой страницы
                all_results = []
                result_components = []
                
                for i, img in enumerate(images):
                    result = self.ocr_processor.extract_text_simple(img)
                    result['page'] = i + 1
                    all_results.append(result)
                    
                    # Создаем компонент результата для страницы
                    page_result = self.create_page_result_card(result, img)
                    result_components.append(page_result)
                
                # Сводная панель
                summary_panel = self.create_summary_panel(all_results, config)
                
                return html.Div([
                    summary_panel,
                    html.Hr(),
                    html.Div(result_components)
                ])
                
            except Exception as e:
                error_panel = dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    f"Ошибка OCR: {str(e)}"
                ], color="danger")
                return error_panel
    
    def create_page_result_card(self, result, img):
        """Создание карточки результата для страницы"""
        # Конвертируем изображение для отображения
        buffer = io.BytesIO()
        img_resized = img.copy()
        img_resized.thumbnail((400, 600), Image.LANCZOS)
        img_resized.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        return dbc.Card([
            dbc.CardHeader(f"📄 Страница {result['page']}"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H6("Извлеченные данные:"),
                        dbc.Table([
                            html.Tbody([
                                html.Tr([html.Td("ФИО:"), html.Td(result['fullname'])]),
                                html.Tr([html.Td("Серия:"), html.Td(result['series'])]),
                                html.Tr([html.Td("Номер:"), html.Td(result['number'])]),
                                html.Tr([html.Td("Рег. номер:"), html.Td(result['registrationnumber'])]),
                                html.Tr([html.Td("Дата выдачи:"), html.Td(result['issuedate'])])
                            ])
                        ], bordered=True, size="sm"),
                        
                        # Показываем сырой текст если есть
                        html.Details([
                            html.Summary("Показать исходный текст OCR"),
                            html.Pre(result.get('raw_text', 'Нет данных'), 
                                   className="small bg-light p-2 mt-2")
                        ])
                    ], width=6),
                    
                    dbc.Col([
                        html.H6("Изображение страницы:"),
                        html.Img(
                            src=f"data:image/png;base64,{img_b64}",
                            style={'width': '100%', 'height': 'auto', 'max-height': '400px'},
                            className="border"
                        )
                    ], width=6)
                ])
            ])
        ], className="mb-4")
    
    def create_summary_panel(self, results, config):
        """Создание сводной панели результатов"""
        total_pages = len(results)
        
        # Создаем DataFrame для экспорта
        export_data = []
        for result in results:
            export_data.append({
                'Страница': result['page'],
                'ФИО': result['fullname'],
                'Серия': result['series'],
                'Номер': result['number'],
                'Рег.номер': result['registrationnumber'],
                'Дата': result['issuedate']
            })
        
        df = pd.DataFrame(export_data)
        
        # Экспорт в CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_b64 = base64.b64encode(csv_buffer.getvalue().encode()).decode()
        
        return dbc.Card([
            dbc.CardHeader("📊 Сводка результатов"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Alert([
                            html.H5(f"Обработано страниц: {total_pages}"),
                            html.P(f"Конфигурация: {config}"),
                            html.P(f"Время: {datetime.now().strftime('%H:%M:%S')}")
                        ], color="info")
                    ], width=6),
                    
                    dbc.Col([
                        html.H6("Экспорт результатов:"),
                        html.A(
                            dbc.Button([
                                html.I(className="fas fa-download me-2"),
                                "Скачать CSV"
                            ], color="success"),
                            href=f"data:text/csv;charset=utf-8;base64,{csv_b64}",
                            download=f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        )
                    ], width=6)
                ])
            ])
        ], className="mb-4")
    
    def run_server(self, debug=True, host='127.0.0.1', port=8050):
        """Запуск сервера"""
        logger.info(f"🚀 Запуск OCR Dashboard на http://{host}:{port}")
        try:
            self.app.run(debug=debug, host=host, port=port)
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")
            self.app.server.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    dashboard = OCRDashboard()
    dashboard.run_server(debug=True)