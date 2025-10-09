"""
OCR движок с Tesseract для распознавания документов об образовании
"""

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from typing import Tuple, Dict, Any
import os


class ImageProcessor:
    """Класс для обработки изображений PDF с улучшенной предобработкой"""
    
    def __init__(self, max_dimension: int = 1200, dpi: int = 300):
        """
        Инициализация процессора изображений
        
        Args:
            max_dimension: Максимальный размер стороны изображения после масштабирования
            dpi: Разрешение для конвертации PDF в изображение
        """
        self.max_dimension = max_dimension
        self.dpi = dpi
    
    def convert_pdf_to_images(self, pdf_path: str):
        """
        Конвертация PDF в список изображений
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            List[Image.Image]: Список изображений страниц
        """
        import fitz
        import io
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Файл {pdf_path} не найден")
        
        images = []
        pdf_document = fitz.open(pdf_path)
        
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            mat = fitz.Matrix(self.dpi/72, self.dpi/72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
        
        pdf_document.close()
        return images
    
    def resize_image(self, img: Image.Image) -> Image.Image:
        """
        Масштабирование изображения с сохранением пропорций
        
        Args:
            img: Исходное изображение
            
        Returns:
            Image.Image: Масштабированное изображение
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
        Улучшение качества изображения
        
        Args:
            img: Исходное изображение
            
        Returns:
            Image.Image: Улучшенное изображение
        """
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.1)
        
        return img
    
    def rotate_image(self, img: Image.Image, rotation_angle: int) -> Image.Image:
        """
        Поворот изображения на заданный угол
        
        Args:
            img: Исходное изображение
            rotation_angle: Угол поворота (90, 180, 270)
            
        Returns:
            Image.Image: Повернутое изображение
        """
        if rotation_angle == 90:
            return img.transpose(Image.ROTATE_90)
        elif rotation_angle == 180:
            return img.transpose(Image.ROTATE_180)
        elif rotation_angle == 270:
            return img.transpose(Image.ROTATE_270)
        return img
    
    def remove_lines_from_region(self, img: Image.Image, aggressive: bool = False) -> Image.Image:
        """
        Удаление горизонтальных линий для улучшения OCR текста на подчеркиваниях
        
        Args:
            img: Область изображения для обработки
            aggressive: Использовать агрессивное удаление линий
            
        Returns:
            Image.Image: Обработанное изображение
        """
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        if aggressive:
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            lines_mask = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
            gray_no_lines = cv2.subtract(gray, lines_mask)
            gray_no_lines = cv2.addWeighted(gray_no_lines, 1.5, gray_no_lines, 0, 0)
        else:
            gray_no_lines = cv2.bilateralFilter(gray, 9, 75, 75)
        
        img_processed = Image.fromarray(gray_no_lines)
        return img_processed


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
        self.image_processor = ImageProcessor()
    
    def preprocess_region(self, region: Image.Image, ocr_params: Dict, 
                         field_name: str = "", config_org: str = "") -> Image.Image:
        """
        Предобработка области для улучшения OCR с учетом типа поля
        
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
        
        if field_name == 'full_name' and 'FINUNIV' in config_org:
            region = self.image_processor.remove_lines_from_region(region, aggressive=True)
        
        if scale_factor > 1:
            new_size = (width * scale_factor, height * scale_factor)
            region = region.resize(new_size, Image.LANCZOS)
        
        enhancer = ImageEnhance.Contrast(region)
        region = enhancer.enhance(contrast_boost)
        
        if field_name == 'registration_number' and scale_factor >= 4:
            enhancer = ImageEnhance.Brightness(region)
            region = enhancer.enhance(1.1)
            region = region.filter(ImageFilter.MedianFilter(size=3))
        
        region = region.filter(ImageFilter.MedianFilter(size=3))
        
        enhancer = ImageEnhance.Sharpness(region)
        region = enhancer.enhance(1.5)
        
        return region
    
    def extract_text(self, img: Image.Image, box: Tuple[int, int, int, int],
                    field_name: str, config: Any) -> str:
        """
        Извлечение текста из области изображения с адаптивными настройками
        
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
        
        if field_name == 'full_name':
            if config.document_type == 'diploma':
                psm = 6
            elif 'FINUNIV' in config.organization and 'v2' in config.document_type:
                psm = 6
            else:
                psm = 7
        elif field_name == 'issue_date' and 'FINUNIV' in config.organization:
            psm = 6
        else:
            psm = 7
        
        try:
            config_str = f'--oem 3 --psm {psm}'
            
            if field_name == 'full_name' or 'date' in field_name:
                lang = 'rus'
            elif field_name == 'series_and_number':
                lang = 'rus+eng'
            else:
                lang = 'rus+eng'
            
            text = pytesseract.image_to_string(region, lang=lang, config=config_str)
            return text.strip()
        except Exception as e:
            print(f"❌ Ошибка OCR: {e}")
            return ""


class DocumentProcessor:
    """Основной процессор для извлечения полей из документов"""
    
    def __init__(self, tesseract_cmd: str = None):
        """
        Инициализация процессора документов
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract (опционально)
        """
        self.image_processor = ImageProcessor()
        self.ocr_engine = OCREngine(tesseract_cmd)
    
    def extract_fields(self, img: Image.Image, config: Any, 
                      uncertainty_engine: Any) -> Dict[str, Any]:
        """
        Извлечение всех полей документа согласно конфигурации
        
        Args:
            img: Изображение документа
            config: Конфигурация документа с координатами полей
            uncertainty_engine: Движок оценки неуверенности распознавания
            
        Returns:
            Dict[str, Any]: Словарь с извлеченными полями и списком неуверенных полей
        """
        result = {}
        uncertainties = []
        
        for field_config in config.fields:
            box = field_config['box']
            field_name = field_config['name']
            
            if not box:
                result[field_name] = "NOT_CONFIGURED"
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
        
        result['_uncertainties'] = uncertainties
        return result
