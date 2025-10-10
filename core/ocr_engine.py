"""
OCR движок с Tesseract для распознавания документов
Версия: 3.1 (Исправлено: config.fields вместо config.get)
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import cv2
import numpy as np
from typing import Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class OCREngine:
    """Движок оптического распознавания символов с адаптивными настройками"""
    
    def __init__(self, tesseract_cmd: str = None):
        """
        Инициализация OCR движка
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract (опционально)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        from core.image_processor import AdvancedImageProcessor
        self.image_processor = AdvancedImageProcessor()
    
    def preprocess_region(self, region: Image.Image, ocr_params: Dict, 
                         field_name: str = "", config_org: str = "") -> Image.Image:
        """
        Предобработка области для улучшения OCR
        
        Args:
            region: Область изображения для распознавания
            ocr_params: Параметры OCR (scale_factor, contrast_boost)
            field_name: Имя поля документа
            config_org: Организация-эмитент документа
            
        Returns:
            Image.Image: Предобработанная область
        """
        scale_factor = ocr_params.get('scale_factor', 3)
        contrast_boost = ocr_params.get('contrast_boost', 1.5)
        
        width, height = region.size
        
        # Удаление линий для ФИО в ФинУниверситете
        if field_name == 'full_name' and 'FINUNIV' in config_org:
            region = self.image_processor.remove_lines_horizontal(region, aggressive=True)
        
        # Масштабирование
        if scale_factor > 1:
            new_size = (width * scale_factor, height * scale_factor)
            region = region.resize(new_size, Image.LANCZOS)
        
        # Контраст
        enhancer = ImageEnhance.Contrast(region)
        region = enhancer.enhance(contrast_boost)
        
        # Дополнительная обработка для регистрационных номеров
        if field_name == 'registration_number' and scale_factor >= 4:
            enhancer = ImageEnhance.Brightness(region)
            region = enhancer.enhance(1.1)
            region = region.filter(ImageFilter.MedianFilter(size=3))
        
        # Медианный фильтр для удаления шума
        region = region.filter(ImageFilter.MedianFilter(size=3))
        
        # Повышение резкости
        enhancer = ImageEnhance.Sharpness(region)
        region = enhancer.enhance(1.5)
        
        return region
    
    def extract_text(self, img: Image.Image, box: Tuple[int, int, int, int],
                    field_name: str, config: Any) -> str:
        """
        Извлечение текста из области изображения
        
        Args:
            img: Исходное изображение документа
            box: Координаты области (x1, y1, x2, y2)
            field_name: Имя поля для извлечения
            config: Конфигурация документа
            
        Returns:
            str: Распознанный текст
        """
        region = img.crop(box)
        region = self.preprocess_region(region, config.ocr_params, field_name, config.organization)
        region = region.convert('L')
        
        # Выбор режима PSM в зависимости от типа поля
        if field_name == 'full_name':
            if config.document_type == 'diploma':
                psm = 6  # Многострочный текст
            elif 'FINUNIV' in config.organization and 'v2' in config.document_type:
                psm = 6
            else:
                psm = 7  # Однострочный текст
        elif field_name == 'issue_date' and 'FINUNIV' in config.organization:
            psm = 6
        else:
            psm = 7
        
        try:
            config_str = f'--oem 3 --psm {psm}'
            
            # Выбор языка распознавания
            if field_name == 'full_name' or 'date' in field_name:
                lang = 'rus'
            elif field_name == 'series_and_number':
                lang = 'rus+eng'
            else:
                lang = 'rus+eng'
            
            text = pytesseract.image_to_string(region, lang=lang, config=config_str)
            return text.strip()
        except Exception as e:
            logger.error(f"Ошибка OCR для поля {field_name}: {e}")
            return ""


class DocumentProcessor:
    """Основной процессор для извлечения полей из документов"""
    
    def __init__(self, tesseract_cmd: str = None):
        """
        Инициализация процессора документов
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract (опционально)
        """
        from core.image_processor import AdvancedImageProcessor
        self.image_processor = AdvancedImageProcessor()
        self.ocr_engine = OCREngine(tesseract_cmd)
    
    def extract_fields(self, img: Image.Image, config: Any, 
                      uncertainty_engine: Any) -> Dict[str, Any]:
        """
        Извлечение всех полей документа согласно конфигурации
        
        Args:
            img: Изображение документа
            config: Конфигурация документа (объект DocumentConfig)
            uncertainty_engine: Движок оценки неуверенности распознавания
            
        Returns:
            Dict[str, Any]: Словарь с извлеченными полями и списком неуверенных полей
        """
        result = {}
        uncertainties = []
        
        # ИСПРАВЛЕНО: config.fields вместо config.get('fields')
        for field_config in config.fields:
            box = field_config['box']
            field_name = field_config['name']
            
            if not box:
                result[field_name] = "NOT_CONFIGURED"
                continue
            
            # Валидация координат
            if not (isinstance(box, (list, tuple)) and len(box) == 4 and 
                   all(isinstance(x, (int, float)) for x in box)):
                logger.warning(f"Некорректные координаты для поля {field_name}: {box}")
                result[field_name] = "INVALID_BOX"
                continue
            
            text = self.ocr_engine.extract_text(img, box, field_name, config)
            
            if field_name == 'series_and_number':
                series, number, uncertain = config.patterns['series_and_number'](text)
                result['series'] = series
                result['number'] = number
                
                if uncertain or uncertainty_engine.should_flag_uncertainty(
                    field_name, text, (series, number)):
                    uncertainties.append({
                        'field': 'series_and_number',
                        'reason': 'Номер подозрительно короткий или были исправления OCR'
                    })
            
            elif field_name == 'registration_number':
                parsed_result, uncertain = config.patterns['registration_number'](text)
                result['registration_number'] = parsed_result
                
                if uncertain or uncertainty_engine.should_flag_uncertainty(
                    field_name, text, parsed_result, uncertain):
                    uncertainties.append({
                        'field': 'registration_number',
                        'reason': 'Критично короткий номер или были исправления OCR'
                    })
            
            elif field_name in config.patterns:
                parsed_result, uncertain = config.patterns[field_name](text)
                result[field_name] = parsed_result
                
                if uncertain or uncertainty_engine.should_flag_uncertainty(
                    field_name, text, parsed_result, uncertain):
                    uncertainties.append({
                        'field': field_name,
                        'reason': 'Низкое качество распознавания или исправления OCR'
                    })
            else:
                result[field_name] = text
        
        result['uncertainties'] = uncertainties
        return result
    
    def display_image_with_boxes(self, img: Image.Image, fields: List[Dict]) -> Image.Image:
        """
        Отображение изображения с рамками полей
        
        Args:
            img: Исходное изображение
            fields: Список полей с координатами
            
        Returns:
            Image.Image: Изображение с нарисованными рамками
        """
        img_copy = img.copy()
        draw = ImageDraw.Draw(img_copy)
        
        colors = ['red', 'green', 'blue', 'orange', 'purple', 'cyan']
        
        for i, field_config in enumerate(fields):
            box = field_config.get('box')
            field_name = field_config.get('name', '')
            
            if box and len(box) == 4:
                color = colors[i % len(colors)]
                draw.rectangle(box, outline=color, width=3)
                
                try:
                    draw.text((box[0], box[1] - 15), field_name, fill=color)
                except Exception as e:
                    logger.debug(f"Не удалось добавить текст к полю {field_name}: {e}")
        
        return img_copy
    
    def crop_field_thumbnail(self, img: Image.Image, box: Tuple[int, int, int, int]) -> Image.Image:
        """
        Вырезание миниатюры поля
        
        Args:
            img: Исходное изображение
            box: Координаты области
            
        Returns:
            Image.Image: Миниатюра поля
        """
        try:
            if box and len(box) == 4 and all(isinstance(x, (int, float)) for x in box):
                return img.crop(box)
            else:
                logger.warning(f"Некорректные координаты box: {box}")
                return Image.new('RGB', (120, 80), 'lightgray')
        except Exception as e:
            logger.error(f"Ошибка вырезания миниатюры: {e}")
            return Image.new('RGB', (120, 80), 'lightgray')
