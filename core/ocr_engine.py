"""
OCR движок для распознавания документов
Основан на Tesseract с оптимизированными настройками для различных типов полей
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
from typing import Dict, Any, Tuple, List, Optional
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCREngine:
    """
    Основной класс для выполнения OCR с настройками под разные типы полей
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Инициализация OCR движка
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу tesseract
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # Настройки OCR для разных типов полей
        self.field_configs = {
            'fullname': {
                'lang': 'rus',
                'psm': 7,  # Treat the image as a single text line
                'oem': 3,  # Default OCR Engine Mode
                'scale_factor': 3,
                'contrast_boost': 1.5
            },
            'seriesandnumber': {
                'lang': 'rus+eng',
                'psm': 7,
                'oem': 3,
                'scale_factor': 4,
                'contrast_boost': 2.0
            },
            'registrationnumber': {
                'lang': 'rus+eng',
                'psm': 7,
                'oem': 3,
                'scale_factor': 4,
                'contrast_boost': 2.0
            },
            'issuedate': {
                'lang': 'rus+eng',
                'psm': 6,  # Uniform block of text
                'oem': 3,
                'scale_factor': 3,
                'contrast_boost': 1.8
            }
        }
    
    def preprocess_region(self, region: Image.Image, field_name: str, 
                         custom_params: Optional[Dict] = None) -> Image.Image:
        """
        Предобработка области изображения для улучшения качества OCR
        
        Args:
            region: Область изображения для обработки
            field_name: Тип поля для применения специфичных настроек
            custom_params: Дополнительные параметры обработки
            
        Returns:
            Обработанное изображение
        """
        # Получаем настройки для типа поля
        config = self.field_configs.get(field_name, self.field_configs['fullname'])
        if custom_params:
            config.update(custom_params)
        
        # Масштабирование
        scale_factor = config.get('scale_factor', 3)
        width, height = region.size
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        region = region.resize((new_width, new_height), Image.LANCZOS)
        
        # Улучшение контрастности
        contrast_boost = config.get('contrast_boost', 1.5)
        enhancer = ImageEnhance.Contrast(region)
        region = enhancer.enhance(contrast_boost)
        
        # Улучшение резкости
        enhancer = ImageEnhance.Sharpness(region)
        region = enhancer.enhance(1.5)
        
        # Повышение яркости для темных областей
        enhancer = ImageEnhance.Brightness(region)
        region = enhancer.enhance(1.1)
        
        # Применение медианного фильтра для устранения шума
        region = region.filter(ImageFilter.MedianFilter(size=3))
        
        # Преобразование в градации серого
        region = region.convert('L')
        
        # Специальная обработка для FinUniv документов (удаление линий)
        if field_name == 'fullname' and custom_params and 'aggressive_line_removal' in custom_params:
            region = self._remove_lines_opencv(region)
        
        return region
    
    def _remove_lines_opencv(self, region: Image.Image) -> Image.Image:
        """
        Удаление горизонтальных линий с помощью OpenCV
        """
        # Конвертируем PIL в OpenCV формат
        img_cv = cv2.cvtColor(np.array(region), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Создаем ядро для обнаружения горизонтальных линий
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        
        # Обнаруживаем горизонтальные линии
        lines_mask = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
        
        # Удаляем линии
        gray_no_lines = cv2.subtract(gray, lines_mask)
        
        # Усиливаем контраст
        gray_no_lines = cv2.addWeighted(gray_no_lines, 1.5, gray_no_lines, 0, 0)
        
        # Конвертируем обратно в PIL
        return Image.fromarray(gray_no_lines)
    
    def extract_text(self, img: Image.Image, box: Tuple[int, int, int, int], 
                    field_name: str, custom_params: Optional[Dict] = None) -> str:
        """
        Извлечение текста из указанной области изображения
        
        Args:
            img: Исходное изображение
            box: Координаты области (x1, y1, x2, y2)
            field_name: Тип поля для применения специфичных настроек OCR
            custom_params: Дополнительные параметры
            
        Returns:
            Распознанный текст
        """
        try:
            # Вырезаем область
            region = img.crop(box)
            
            # Предобрабатываем область
            region = self.preprocess_region(region, field_name, custom_params)
            
            # Получаем конфигурацию OCR для типа поля
            config = self.field_configs.get(field_name, self.field_configs['fullname'])
            if custom_params:
                config.update(custom_params)
            
            # Формируем строку конфигурации tesseract
            lang = config.get('lang', 'rus')
            psm = config.get('psm', 7)
            oem = config.get('oem', 3)
            
            config_str = f'--oem {oem} --psm {psm}'
            
            # Выполняем OCR
            text = pytesseract.image_to_string(region, lang=lang, config=config_str)
            
            logger.debug(f"OCR результат для {field_name}: '{text.strip()}'")
            return text.strip()
            
        except Exception as e:
            logger.error(f"Ошибка OCR для поля {field_name}: {e}")
            return ""


class ImageProcessor:
    """
    Класс для обработки и подготовки изображений
    """
    
    def __init__(self, max_dimension: int = 1200, dpi: int = 300):
        """
        Args:
            max_dimension: Максимальный размер изображения по большей стороне
            dpi: DPI для конвертации PDF
        """
        self.max_dimension = max_dimension
        self.dpi = dpi
    
    def resize_image(self, img: Image.Image) -> Image.Image:
        """
        Изменение размера изображения с сохранением пропорций
        """
        width, height = img.size
        max_dim = max(width, height)
        
        if max_dim > self.max_dimension:
            scale = self.max_dimension / max_dim
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = img.resize((new_width, new_height), Image.LANCZOS)
        
        return img
    
    def enhance_image(self, img: Image.Image) -> Image.Image:
        """
        Общее улучшение качества изображения
        """
        # Увеличение контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        
        # Увеличение резкости
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.1)
        
        return img
    
    def rotate_image(self, img: Image.Image, rotation_angle: int) -> Image.Image:
        """
        Поворот изображения на указанный угол
        """
        if rotation_angle == 90:
            return img.transpose(Image.ROTATE_90)
        elif rotation_angle == 180:
            return img.transpose(Image.ROTATE_180)
        elif rotation_angle == 270:
            return img.transpose(Image.ROTATE_270)
        
        return img


class DocumentProcessor:
    """
    Основной процессор документов, объединяющий OCR и обработку изображений
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Args:
            tesseract_cmd: Путь к исполняемому файлу tesseract
        """
        self.image_processor = ImageProcessor()
        self.ocr_engine = OCREngine(tesseract_cmd)
    
    def extract_fields(self, img: Image.Image, config: Dict, 
                      uncertainty_engine: Any = None) -> Dict[str, Any]:
        """
        Извлечение всех полей из документа
        
        Args:
            img: Изображение документа
            config: Конфигурация документа с описанием полей
            uncertainty_engine: Движок оценки неуверенности
            
        Returns:
            Словарь с извлеченными данными
        """
        result = {}
        uncertainties = []
        
        # Обрабатываем каждое поле согласно конфигурации
        for field_config in config.get('fields', []):
            box = field_config.get('box')
            field_name = field_config.get('name')
            
            if not box:
                result[field_name] = "NOT_CONFIGURED"
                continue
            
            # Извлекаем текст
            raw_text = self.ocr_engine.extract_text(
                img, box, field_name, config.get('ocr_params')
            )
            
            # Применяем парсер если есть
            if field_name in config.get('patterns', {}):
                parser_func = config['patterns'][field_name]
                
                if field_name == 'seriesandnumber':
                    # Специальная обработка для серии и номера
                    series, number, uncertain = parser_func(raw_text)
                    result['series'] = series
                    result['number'] = number
                    
                    if uncertain and uncertainty_engine:
                        if uncertainty_engine.should_flag_uncertainty(
                            field_name, raw_text, (series, number)
                        ):
                            uncertainties.append({
                                'field': field_name,
                                'reason': 'OCR_UNCERTAINTY'
                            })
                else:
                    # Обычная обработка
                    parsed_result, uncertain = parser_func(raw_text)
                    result[field_name] = parsed_result
                    
                    if uncertain and uncertainty_engine:
                        if uncertainty_engine.should_flag_uncertainty(
                            field_name, raw_text, parsed_result
                        ):
                            uncertainties.append({
                                'field': field_name,
                                'reason': 'OCR_UNCERTAINTY'
                            })
            else:
                # Без парсера - возвращаем сырой текст
                result[field_name] = raw_text
        
        result['uncertainties'] = uncertainties
        return result
    
    def display_image_with_boxes(self, img: Image.Image, fields: List[Dict]) -> Image.Image:
        """
        Отображение изображения с выделенными областями полей
        """
        img_copy = img.copy()
        draw = ImageDraw.Draw(img_copy)
        
        colors = ['red', 'green', 'blue', 'orange', 'purple']
        
        for i, field_config in enumerate(fields):
            box = field_config.get('box')
            field_name = field_config.get('name')
            
            if box:
                color = colors[i % len(colors)]
                draw.rectangle(box, outline=color, width=3)
                # Добавляем подпись поля
                draw.text((box[0], box[1] - 25), field_name, fill=color)
        
        return img_copy