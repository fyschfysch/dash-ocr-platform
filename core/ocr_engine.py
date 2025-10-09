"""
Полнофункциональный OCR движок для документов
Основан на исходном коде с улучшениями для Dash-интеграции
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
import cv2
import numpy as np
import logging
from typing import Dict, List, Tuple, Any, Optional
import io
import base64
from datetime import datetime

# Внутренние импорты
from core.config import DocumentConfig, UncertaintyEngine, get_field_description
from core.image_processor import AdvancedImageProcessor, RegionProcessor

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Основной процессор документов с полной функциональностью
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Инициализация OCR движка
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract
        """
        # Настройка Tesseract
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            logger.info(f"Tesseract установлен: {tesseract_cmd}")
        
        # Инициализация процессоров изображений
        self.image_processor = AdvancedImageProcessor()
        self.region_processor = RegionProcessor()
        
        # Проверка доступности Tesseract
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract версия: {version}")
            self.tesseract_available = True
        except Exception as e:
            logger.error(f"Tesseract недоступен: {e}")
            self.tesseract_available = False
        
        # Настройки OCR по умолчанию
        self.default_ocr_params = {
            'scale_factor': 3,
            'contrast_boost': 1.5,
            'sharpness_boost': 1.2,
            'brightness_boost': 1.1,
            'denoise_method': 'bilateral'
        }
        
        logger.info("DocumentProcessor инициализирован")
    
    def extract_fields(self, img: Image.Image, config: DocumentConfig, 
                      uncertainty_engine: UncertaintyEngine) -> Dict[str, Any]:
        """
        Извлечение полей из изображения документа
        
        Args:
            img: Изображение документа
            config: Конфигурация документа
            uncertainty_engine: Движок определения неуверенности
            
        Returns:
            Словарь с извлеченными полями и метаданными
        """
        if not self.tesseract_available:
            return self._create_error_result("Tesseract OCR недоступен")
        
        result = {
            'extraction_time': datetime.now().isoformat(),
            'config_used': config.config_id,
            'uncertainties': []
        }
        
        uncertainties = []
        
        logger.info(f"Начало извлечения полей для {config.name}")
        
        # Обрабатываем каждое поле согласно конфигурации
        for field_config in config.fields:
            field_name = field_config['name']
            box = field_config.get('box')
            
            logger.debug(f"Обработка поля: {field_name}")
            
            if not box:
                logger.warning(f"Поле {field_name} не имеет координат")
                result[field_name] = 'NOT_CONFIGURED'
                uncertainties.append({
                    'field': field_name,
                    'reason': 'Координаты поля не настроены',
                    'original_text': '',
                    'confidence': 0.0
                })
                continue
            
            try:
                # Извлекаем область поля
                region = img.crop(box)
                
                # Предобработка региона
                processed_region = self._preprocess_field_region(
                    region, field_name, config
                )
                
                # OCR текста
                extracted_text = self._extract_text_from_region(
                    processed_region, field_name, config
                )
                
                # Парсинг через специализированные парсеры
                if field_name == 'seriesandnumber':
                    # Специальная обработка серии и номера
                    series, number, is_uncertain = self._parse_series_number(
                        extracted_text, config, uncertainty_engine
                    )
                    
                    result['series'] = series
                    result['number'] = number
                    result[field_name] = f"{series} {number}".strip()
                    
                    if is_uncertain:
                        uncertainties.append({
                            'field': 'seriesandnumber',
                            'reason': 'Низкая уверенность в серии/номере',
                            'original_text': extracted_text,
                            'parsed_value': f"{series} {number}",
                            'confidence': 0.5
                        })
                
                elif field_name in config.patterns:
                    # Обработка через парсеры из конфигурации
                    parsed_value, is_uncertain = config.patterns[field_name](extracted_text)
                    result[field_name] = parsed_value
                    
                    # Проверка неуверенности
                    if is_uncertain or uncertainty_engine.should_flag_uncertainty(
                        field_name, extracted_text, parsed_value, is_uncertain
                    ):
                        uncertainties.append({
                            'field': field_name,
                            'reason': 'Требует проверки после парсинга',
                            'original_text': extracted_text,
                            'parsed_value': parsed_value,
                            'confidence': 0.6
                        })
                
                else:
                    # Простое сохранение текста без парсинга
                    result[field_name] = extracted_text.strip()
                    
                    # Базовая проверка качества
                    if not extracted_text.strip() or len(extracted_text.strip()) < 2:
                        uncertainties.append({
                            'field': field_name,
                            'reason': 'Извлечен пустой или очень короткий текст',
                            'original_text': extracted_text,
                            'confidence': 0.3
                        })
                
                logger.debug(f"Поле {field_name}: '{result.get(field_name, '')[:50]}...'")
                
            except Exception as e:
                logger.error(f"Ошибка обработки поля {field_name}: {e}")
                result[field_name] = 'EXTRACTION_ERROR'
                uncertainties.append({
                    'field': field_name,
                    'reason': f'Ошибка извлечения: {str(e)}',
                    'original_text': '',
                    'confidence': 0.0
                })
        
        result['uncertainties'] = uncertainties
        result['total_uncertainties'] = len(uncertainties)
        
        logger.info(f"Извлечение завершено. Неуверенностей: {len(uncertainties)}")
        
        return result
    
    def _preprocess_field_region(self, region: Image.Image, field_name: str, 
                                config: DocumentConfig) -> Image.Image:
        """
        Предобработка области поля для улучшения качества OCR
        """
        # Получаем параметры OCR из конфигурации
        ocr_params = config.ocr_params or self.default_ocr_params
        
        # Создаем параметры для конкретного поля
        field_params = ocr_params.copy()
        
        # Специальные настройки для разных типов полей
        if field_name == 'fullname':
            # Для ФИО увеличиваем масштаб и контраст
            field_params['scale_factor'] = 4
            field_params['contrast_boost'] = 1.8
            
            # Для ФинУниверситета агрессивно удаляем линии
            if 'FINUNIV' in config.organization:
                field_params['aggressive_line_removal'] = True
        
        elif field_name == 'seriesandnumber':
            # Для серии/номера фокус на резкости
            field_params['scale_factor'] = 3
            field_params['sharpness_boost'] = 1.5
            field_params['denoise_method'] = 'median'
        
        elif field_name == 'issuedate':
            # Для даты стандартная обработка
            field_params['scale_factor'] = 3
            field_params['contrast_boost'] = 1.3
        
        # Применяем предобработку через RegionProcessor
        processed_region = self.region_processor.preprocess_region_for_field(
            region, (0, 0, region.width, region.height), field_name, field_params
        )
        
        return processed_region
    
    def _extract_text_from_region(self, region: Image.Image, field_name: str, 
                                config: DocumentConfig) -> str:
        """
        Извлечение текста из предобработанной области
        """
        # Настройки PSM (Page Segmentation Mode) для разных типов полей
        if field_name == 'fullname':
            if config.document_type == 'diploma':
                psm = 6  # Один блок текста
            elif 'FINUNIV' in config.organization and 'v2' in config.name:
                psm = 6  # Многострочное ФИО
            else:
                psm = 7  # Одна строка текста
        
        elif field_name == 'issuedate' and 'FINUNIV' in config.organization:
            psm = 6  # Блок текста для даты
        
        elif field_name == 'seriesandnumber':
            psm = 7  # Одна строка для серии/номера
        
        else:
            psm = 7  # По умолчанию одна строка
        
        # Настройки языка
        if field_name == 'seriesandnumber':
            lang = 'rus+eng'  # Русский и английский для серий
        else:
            lang = 'rus'  # Только русский для остальных полей
        
        # Дополнительные параметры Tesseract
        config_str = f'--oem 3 --psm {psm} -c tessedit_char_whitelist='
        
        # Ограничения символов для разных полей
        if field_name == 'seriesandnumber':
            config_str += '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя -'
        elif field_name == 'registrationnumber':
            config_str += '0123456789АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя.-/'
        else:
            config_str = f'--oem 3 --psm {psm}'  # Без ограничений для остальных
        
        try:
            # Выполняем OCR
            text = pytesseract.image_to_string(
                region, lang=lang, config=config_str
            ).strip()
            
            # Базовая очистка результата
            text = self._clean_extracted_text(text, field_name)
            
            logger.debug(f"OCR для {field_name}: '{text[:50]}...'")
            return text
            
        except Exception as e:
            logger.error(f"Ошибка Tesseract для поля {field_name}: {e}")
            return ''
    
    def _clean_extracted_text(self, text: str, field_name: str) -> str:
        """
        Базовая очистка извлеченного текста
        """
        if not text:
            return ''
        
        # Убираем лишние пробелы и переносы
        text = ' '.join(text.split())
        
        # Специфическая очистка для разных полей
        if field_name == 'seriesandnumber':
            # Убираем лишние символы из серии/номера
            import re
            text = re.sub(r'[^\w\s-]', ' ', text)
            text = ' '.join(text.split())
        
        elif field_name == 'registrationnumber':
            # Сохраняем цифры, буквы, точки, дефисы
            import re
            text = re.sub(r'[^\w\s.-]', '', text)
        
        return text.strip()
    
    def _parse_series_number(self, text: str, config: DocumentConfig,
                           uncertainty_engine: UncertaintyEngine) -> Tuple[str, str, bool]:
        """
        Парсинг серии и номера через конфигурационные парсеры
        """
        try:
            if 'seriesandnumber' in config.patterns:
                series, number, is_uncertain = config.patterns['seriesandnumber'](text)
                
                # Дополнительная проверка через uncertainty engine
                additional_uncertainty = uncertainty_engine.should_flag_uncertainty(
                    'seriesandnumber', text, (series, number), is_uncertain
                )
                
                return series, number, is_uncertain or additional_uncertainty
            
            else:
                # Fallback парсинг если нет конфигурации
                parts = text.split()
                if len(parts) >= 2:
                    return parts[0], ' '.join(parts[1:]), False
                else:
                    return text, '', True
                
        except Exception as e:
            logger.error(f"Ошибка парсинга серии/номера: {e}")
            return '', '', True
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """
        Создание результата с ошибкой
        """
        return {
            'error': error_message,
            'extraction_time': datetime.now().isoformat(),
            'total_uncertainties': 0,
            'uncertainties': []
        }
    
    def display_image_with_boxes(self, img: Image.Image, fields: List[Dict]) -> Image.Image:
        """
        Отображение изображения с рамками полей для отладки
        
        Args:
            img: Исходное изображение
            fields: Список конфигураций полей с координатами
            
        Returns:
            Изображение с нарисованными рамками полей
        """
        img_with_boxes = img.copy()
        draw = ImageDraw.Draw(img_with_boxes)
        
        # Цвета для разных полей
        colors = [
            'red', 'blue', 'green', 'orange', 'purple', 
            'brown', 'pink', 'gray', 'olive', 'navy'
        ]
        
        try:
            # Пытаемся загрузить шрифт
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            try:
                font = ImageFont.load_default()
            except:
                font = None
        
        for i, field_config in enumerate(fields):
            box = field_config.get('box')
            name = field_config.get('name', f'field_{i}')
            display_name = get_field_description(name)
            
            if not box or len(box) != 4:
                continue
            
            color = colors[i % len(colors)]
            
            # Рисуем рамку поля
            draw.rectangle(box, outline=color, width=3)
            
            # Подпись поля
            text_x, text_y = box[0], max(0, box[1] - 25)
            
            if font:
                draw.text((text_x, text_y), display_name, fill=color, font=font)
            else:
                draw.text((text_x, text_y), display_name, fill=color)
        
        return img_with_boxes
    
    def crop_field_thumbnail(self, img: Image.Image, box: Tuple[int, int, int, int], 
                           target_size: Tuple[int, int] = (120, 80)) -> Image.Image:
        """
        Вырезание миниатюры поля для отображения в таблице результатов
        
        Args:
            img: Исходное изображение
            box: Координаты поля (x1, y1, x2, y2)
            target_size: Размер миниатюры
            
        Returns:
            Миниатюра поля
        """
        try:
            # Вырезаем область поля
            region = img.crop(box)
            
            # Создаем миниатюру с сохранением пропорций
            region.thumbnail(target_size, Image.LANCZOS)
            
            # Создаем новое изображение с белым фоном нужного размера
            thumbnail = Image.new('RGB', target_size, 'white')
            
            # Центрируем миниатюру
            x_offset = (target_size[0] - region.width) // 2
            y_offset = (target_size[1] - region.height) // 2
            thumbnail.paste(region, (x_offset, y_offset))
            
            return thumbnail
            
        except Exception as e:
            logger.error(f"Ошибка создания миниатюры: {e}")
            # Возвращаем пустое изображение в случае ошибки
            return Image.new('RGB', target_size, 'lightgray')
    
    def get_confidence_score(self, region: Image.Image, field_name: str) -> float:
        """
        Получение оценки уверенности OCR для региона
        
        Args:
            region: Область изображения
            field_name: Название поля
            
        Returns:
            Оценка уверенности от 0.0 до 1.0
        """
        if not self.tesseract_available:
            return 0.0
        
        try:
            # Получаем детальные данные OCR с уверенностью
            data = pytesseract.image_to_data(region, output_type=pytesseract.Output.DICT)
            
            # Вычисляем среднюю уверенность
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            
            if confidences:
                avg_confidence = sum(confidences) / len(confidences)
                return min(avg_confidence / 100.0, 1.0)
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Ошибка получения уверенности: {e}")
            return 0.0
    
    def export_results_to_dict(self, results: List[Dict]) -> Dict[str, Any]:
        """
        Экспорт результатов в структурированный словарь
        
        Args:
            results: Список результатов по страницам
            
        Returns:
            Структурированный словарь для экспорта
        """
        export_data = {
            'export_time': datetime.now().isoformat(),
            'total_pages': len(results),
            'total_uncertainties': sum(len(r.get('uncertainties', [])) for r in results),
            'pages': []
        }
        
        for result in results:
            page_data = {
                'page_number': result.get('page', 1),
                'extraction_time': result.get('extraction_time'),
                'config_used': result.get('config_used'),
                'fields': {},
                'uncertainties': result.get('uncertainties', [])
            }
            
            # Копируем все поля кроме служебных
            for key, value in result.items():
                if key not in ['page', 'extraction_time', 'config_used', 'uncertainties', 
                              'image_b64', 'total_uncertainties']:
                    page_data['fields'][key] = value
            
            export_data['pages'].append(page_data)
        
        return export_data


class OCRDebugger:
    """
    Утилиты для отладки OCR процесса
    """
    
    @staticmethod
    def analyze_field_extraction(processor: DocumentProcessor, img: Image.Image, 
                               field_config: Dict, config: DocumentConfig) -> Dict[str, Any]:
        """
        Детальный анализ извлечения конкретного поля
        """
        field_name = field_config['name']
        box = field_config.get('box')
        
        if not box:
            return {'error': 'Поле не имеет координат'}
        
        analysis = {
            'field_name': field_name,
            'box': box,
            'region_size': (box[2] - box[0], box[3] - box[1])
        }
        
        # Извлекаем и анализируем регион
        region = img.crop(box)
        analysis['original_region_size'] = region.size
        
        # Предобработка
        processed_region = processor._preprocess_field_region(region, field_name, config)
        analysis['processed_region_size'] = processed_region.size
        
        # OCR
        extracted_text = processor._extract_text_from_region(processed_region, field_name, config)
        analysis['extracted_text'] = extracted_text
        analysis['text_length'] = len(extracted_text)
        
        # Уверенность
        confidence = processor.get_confidence_score(processed_region, field_name)
        analysis['confidence'] = confidence
        
        return analysis
    
    @staticmethod
    def save_debug_images(img: Image.Image, results: List[Dict], 
                         output_dir: str = 'debug_output') -> bool:
        """
        Сохранение отладочных изображений
        """
        try:
            import os
            os.makedirs(output_dir, exist_ok=True)
            
            # Сохраняем исходное изображение
            img.save(os.path.join(output_dir, 'original.png'))
            
            # Сохраняем изображение с рамками
            # (требует конфигурацию полей)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения отладочных изображений: {e}")
            return False