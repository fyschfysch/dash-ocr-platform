"""
Расширенный процессор изображений для OCR платформы
Включает предобработку PDF, улучшение качества, коррекцию искажений
"""

import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageDraw, ImageFilter, ImageOps
import cv2
import numpy as np
import io
import base64
import logging
from typing import List, Dict, Tuple, Optional, Any, Union
from pathlib import Path
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)


class AdvancedImageProcessor:
    """
    Продвинутый процессор изображений с полным набором возможностей
    """
    
    def __init__(self, max_dimension: int = 1200, dpi: int = 300):
        """
        Инициализация процессора
        
        Args:
            max_dimension: Максимальный размер изображения по длинной стороне
            dpi: DPI для конвертации PDF
        """
        self.max_dimension = max_dimension
        self.dpi = dpi
        
        # Параметры по умолчанию
        self.default_enhancement = {
            'contrast': 1.2,
            'sharpness': 1.1,
            'brightness': 1.05,
            'color': 1.0
        }
        
        logger.info(f"AdvancedImageProcessor инициализирован: {max_dimension}px, {dpi}dpi")
    
    def convert_pdf_from_path(self, pdf_path: str) -> List[Image.Image]:
        """
        Конвертация PDF файла в список изображений
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Список изображений PIL
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")
        
        try:
            images = []
            pdf_document = fitz.open(pdf_path)
            
            logger.info(f"Конвертация PDF: {pdf_path}, страниц: {len(pdf_document)}")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Матрица для масштабирования (DPI)
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Конвертация в PIL Image
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                
                logger.debug(f"Страница {page_num + 1}: {img.size}")
                images.append(img)
            
            pdf_document.close()
            return images
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF {pdf_path}: {e}")
            raise
    
    def convert_pdf_from_bytes(self, pdf_bytes: bytes) -> List[Image.Image]:
        """
        Конвертация PDF из байтов в список изображений
        
        Args:
            pdf_bytes: Байты PDF файла
            
        Returns:
            Список изображений PIL
        """
        try:
            images = []
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            logger.info(f"Конвертация PDF из байтов, страниц: {len(pdf_document)}")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Матрица для высокого качества
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                # Конвертация в PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Конвертируем в RGB если нужно
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                logger.debug(f"Страница {page_num + 1}: {img.size}, mode: {img.mode}")
                images.append(img)
            
            pdf_document.close()
            return images
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF из байтов: {e}")
            raise
    
    def resize_image(self, img: Image.Image, target_size: Optional[Tuple[int, int]] = None) -> Image.Image:
        """
        Изменение размера изображения с сохранением пропорций
        
        Args:
            img: Исходное изображение
            target_size: Целевой размер (width, height) или None для авто
            
        Returns:
            Масштабированное изображение
        """
        if target_size:
            resized = img.resize(target_size, Image.LANCZOS)
            logger.debug(f"Изображение изменено: {img.size} -> {resized.size}")
            return resized
        
        # Автоматическое масштабирование по максимальной стороне
        width, height = img.size
        max_dim = max(width, height)
        
        if max_dim > self.max_dimension:
            scale = self.max_dimension / max_dim
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            resized = img.resize((new_width, new_height), Image.LANCZOS)
            logger.debug(f"Изображение масштабировано: {img.size} -> {resized.size}")
            return resized
        
        return img
    
    def enhance_image_basic(self, img: Image.Image) -> Image.Image:
        """
        Базовое улучшение изображения
        
        Args:
            img: Исходное изображение
            
        Returns:
            Улучшенное изображение
        """
        enhanced = img.copy()
        
        # Контраст
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(self.default_enhancement['contrast'])
        
        # Резкость
        enhancer = ImageEnhance.Sharpness(enhanced)
        enhanced = enhancer.enhance(self.default_enhancement['sharpness'])
        
        # Яркость
        enhancer = ImageEnhance.Brightness(enhanced)
        enhanced = enhancer.enhance(self.default_enhancement['brightness'])
        
        return enhanced
    
    def enhance_image_advanced(self, img: Image.Image, params: Optional[Dict[str, float]] = None) -> Image.Image:
        """
        Продвинутое улучшение изображения с настраиваемыми параметрами
        
        Args:
            img: Исходное изображение
            params: Параметры улучшения
            
        Returns:
            Улучшенное изображение
        """
        if not params:
            params = self.default_enhancement
        
        enhanced = img.copy()
        
        # Применяем улучшения в определенном порядке
        enhancement_order = ['brightness', 'contrast', 'color', 'sharpness']
        
        for enhancement in enhancement_order:
            if enhancement in params:
                factor = params[enhancement]
                
                if enhancement == 'brightness':
                    enhancer = ImageEnhance.Brightness(enhanced)
                elif enhancement == 'contrast':
                    enhancer = ImageEnhance.Contrast(enhanced)
                elif enhancement == 'color':
                    enhancer = ImageEnhance.Color(enhanced)
                elif enhancement == 'sharpness':
                    enhancer = ImageEnhance.Sharpness(enhanced)
                else:
                    continue
                
                enhanced = enhancer.enhance(factor)
                logger.debug(f"Применено {enhancement}: {factor}")
        
        return enhanced
    
    def rotate_image(self, img: Image.Image, rotation_angle: int) -> Image.Image:
        """
        Поворот изображения на заданный угол
        
        Args:
            img: Исходное изображение
            rotation_angle: Угол поворота (0, 90, 180, 270)
            
        Returns:
            Повернутое изображение
        """
        if rotation_angle == 90:
            rotated = img.transpose(Image.ROTATE_90)
        elif rotation_angle == 180:
            rotated = img.transpose(Image.ROTATE_180)
        elif rotation_angle == 270:
            rotated = img.transpose(Image.ROTATE_270)
        else:
            rotated = img
        
        if rotation_angle != 0:
            logger.debug(f"Изображение повернуто на {rotation_angle}°")
        
        return rotated
    
    def correct_skew(self, img: Image.Image, max_angle: float = 10.0) -> Image.Image:
        """
        Коррекция наклона изображения
        
        Args:
            img: Исходное изображение
            max_angle: Максимальный угол поиска наклона
            
        Returns:
            Изображение с исправленным наклоном
        """
        try:
            # Конвертируем в OpenCV формат
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Детекция наклона через проективное преобразование Hough
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None:
                angles = []
                for line in lines:
                    rho, theta = line[0]
                    angle = np.degrees(theta) - 90
                    if abs(angle) <= max_angle:
                        angles.append(angle)
                
                if angles:
                    # Находим медианный угол
                    median_angle = np.median(angles)
                    
                    if abs(median_angle) > 0.5:  # Только если наклон существенный
                        # Поворачиваем изображение
                        rotated = img.rotate(-median_angle, expand=True, fillcolor='white')
                        logger.debug(f"Скорректирован наклон: {median_angle:.2f}°")
                        return rotated
            
            return img
            
        except Exception as e:
            logger.warning(f"Ошибка коррекции наклона: {e}")
            return img
    
    def remove_noise(self, img: Image.Image, method: str = 'bilateral') -> Image.Image:
        """
        Удаление шума с изображения
        
        Args:
            img: Исходное изображение
            method: Метод фильтрации ('bilateral', 'gaussian', 'median')
            
        Returns:
            Очищенное от шума изображение
        """
        try:
            # Конвертируем в OpenCV
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            if method == 'bilateral':
                # Билатеральный фильтр (сохраняет края)
                filtered = cv2.bilateralFilter(img_cv, 9, 75, 75)
            elif method == 'gaussian':
                # Гауссовый фильтр
                filtered = cv2.GaussianBlur(img_cv, (5, 5), 0)
            elif method == 'median':
                # Медианный фильтр
                filtered = cv2.medianBlur(img_cv, 3)
            else:
                filtered = img_cv
            
            # Конвертируем обратно в PIL
            result = Image.fromarray(cv2.cvtColor(filtered, cv2.COLOR_BGR2RGB))
            logger.debug(f"Применена фильтрация: {method}")
            return result
            
        except Exception as e:
            logger.warning(f"Ошибка фильтрации {method}: {e}")
            return img
    
    def remove_lines_horizontal(self, img: Image.Image, aggressive: bool = False) -> Image.Image:
        """
        Удаление горизонтальных линий (полей для подписей)
        
        Args:
            img: Исходное изображение
            aggressive: Агрессивное удаление
            
        Returns:
            Изображение без горизонтальных линий
        """
        try:
            # Конвертируем в OpenCV
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            if aggressive:
                # Создаем горизонтальное ядро для морфологии
                horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
                
                # Находим горизонтальные линии
                lines_mask = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
                
                # Удаляем линии
                gray_no_lines = cv2.subtract(gray, lines_mask)
                
                # Усиливаем контраст
                gray_no_lines = cv2.addWeighted(gray_no_lines, 1.5, gray_no_lines, 0, 0)
            else:
                # Мягкое удаление через билатеральный фильтр
                gray_no_lines = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Конвертируем обратно в PIL
            result = Image.fromarray(gray_no_lines)
            if result.mode != 'RGB':
                result = result.convert('RGB')
            
            logger.debug(f"Удалены горизонтальные линии (aggressive={aggressive})")
            return result
            
        except Exception as e:
            logger.warning(f"Ошибка удаления линий: {e}")
            return img
    
    def adaptive_threshold(self, img: Image.Image, method: str = 'gaussian') -> Image.Image:
        """
        Адаптивная бинаризация изображения
        
        Args:
            img: Исходное изображение
            method: Метод ('gaussian' или 'mean')
            
        Returns:
            Бинаризованное изображение
        """
        try:
            # Конвертируем в оттенки серого
            if img.mode != 'L':
                gray = img.convert('L')
            else:
                gray = img
            
            # Конвертируем в OpenCV
            gray_cv = np.array(gray)
            
            if method == 'gaussian':
                thresh = cv2.adaptiveThreshold(
                    gray_cv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )
            else:
                thresh = cv2.adaptiveThreshold(
                    gray_cv, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )
            
            # Конвертируем обратно
            result = Image.fromarray(thresh)
            if result.mode != 'RGB':
                result = result.convert('RGB')
            
            logger.debug(f"Применена адаптивная бинаризация: {method}")
            return result
            
        except Exception as e:
            logger.warning(f"Ошибка бинаризации: {e}")
            return img
    
    def crop_with_margin(self, img: Image.Image, box: Tuple[int, int, int, int], 
                        margin: int = 5) -> Image.Image:
        """
        Вырезание области с отступами
        
        Args:
            img: Исходное изображение
            box: Координаты области (x1, y1, x2, y2)
            margin: Отступ в пикселях
            
        Returns:
            Вырезанная область с отступами
        """
        x1, y1, x2, y2 = box
        width, height = img.size
        
        # Добавляем отступы с проверкой границ
        x1 = max(0, x1 - margin)
        y1 = max(0, y1 - margin)
        x2 = min(width, x2 + margin)
        y2 = min(height, y2 + margin)
        
        cropped = img.crop((x1, y1, x2, y2))
        logger.debug(f"Вырезана область: {box} -> {(x1, y1, x2, y2)} с отступом {margin}px")
        return cropped


class ImageAnalyzer:
    """
    Анализатор качества изображений
    """
    
    @staticmethod
    def analyze_image_quality(img: Image.Image) -> Dict[str, Any]:
        """
        Комплексный анализ качества изображения
        
        Args:
            img: Изображение для анализа
            
        Returns:
            Словарь с метриками качества
        """
        try:
            # Базовые характеристики
            width, height = img.size
            total_pixels = width * height
            
            # Конвертируем для анализа
            gray = img.convert('L') if img.mode != 'L' else img
            gray_array = np.array(gray)
            
            # Метрики
            analysis = {
                'width': width,
                'height': height,
                'total_pixels': total_pixels,
                'mode': img.mode,
                'format': getattr(img, 'format', 'Unknown')
            }
            
            # Анализ яркости
            analysis['brightness'] = float(np.mean(gray_array))
            analysis['brightness_std'] = float(np.std(gray_array))
            
            # Анализ контраста
            analysis['contrast'] = float(np.std(gray_array))
            analysis['dynamic_range'] = int(np.max(gray_array)) - int(np.min(gray_array))
            
            # Анализ резкости (через градиент Лапласа)
            laplacian_var = cv2.Laplacian(gray_array, cv2.CV_64F).var()
            analysis['sharpness'] = float(laplacian_var)
            
            # Общая оценка качества (0-1)
            quality_score = ImageAnalyzer._calculate_quality_score(analysis)
            analysis['quality_score'] = quality_score
            
            return analysis
            
        except Exception as e:
            logger.error(f"Ошибка анализа качества: {e}")
            return {
                'width': img.size[0] if img else 0,
                'height': img.size[1] if img else 0,
                'error': str(e),
                'quality_score': 0.0
            }
    
    @staticmethod
    def _calculate_quality_score(analysis: Dict[str, Any]) -> float:
        """
        Вычисление общей оценки качества изображения
        """
        score = 1.0
        
        # Штрафы за плохие характеристики
        if analysis['brightness'] < 50 or analysis['brightness'] > 200:
            score -= 0.2  # Слишком темное или светлое
        
        if analysis['contrast'] < 30:
            score -= 0.3  # Низкий контраст
        
        if analysis['sharpness'] < 100:
            score -= 0.2  # Размытость
        
        if analysis['dynamic_range'] < 100:
            score -= 0.2  # Узкий диапазон яркости
        
        return max(0.0, score)
    
    @staticmethod
    def suggest_improvements(analysis: Dict[str, Any]) -> List[str]:
        """
        Предложения по улучшению качества изображения
        
        Args:
            analysis: Результат анализа качества
            
        Returns:
            Список рекомендаций
        """
        suggestions = []
        
        if analysis.get('brightness', 128) < 80:
            suggestions.append("Увеличить яркость изображения")
        elif analysis.get('brightness', 128) > 180:
            suggestions.append("Уменьшить яркость изображения")
        
        if analysis.get('contrast', 50) < 40:
            suggestions.append("Повысить контраст для лучшей читаемости")
        
        if analysis.get('sharpness', 200) < 150:
            suggestions.append("Применить фильтр резкости")
        
        if analysis.get('dynamic_range', 150) < 120:
            suggestions.append("Улучшить динамический диапазон")
        
        # Проверка размера
        total_pixels = analysis.get('total_pixels', 0)
        if total_pixels < 500000:  # Меньше ~700x700
            suggestions.append("Увеличить разрешение изображения")
        
        return suggestions


class RegionProcessor:
    """
    Специализированный процессор для обработки областей полей
    """
    
    def __init__(self):
        self.field_specific_params = {
            'fullname': {
                'scale_factor': 4,
                'contrast_boost': 1.8,
                'remove_lines': True,
                'noise_reduction': 'bilateral'
            },
            'seriesandnumber': {
                'scale_factor': 3,
                'contrast_boost': 1.6,
                'sharpness_boost': 1.5,
                'noise_reduction': 'median'
            },
            'registrationnumber': {
                'scale_factor': 3,
                'contrast_boost': 1.4,
                'adaptive_threshold': True
            },
            'issuedate': {
                'scale_factor': 3,
                'contrast_boost': 1.3,
                'brightness_boost': 1.1
            }
        }
    
    def preprocess_region_for_field(self, img: Image.Image, box: Tuple[int, int, int, int],
                                  field_name: str, custom_params: Optional[Dict] = None) -> Image.Image:
        """
        Предобработка области изображения для конкретного поля
        
        Args:
            img: Исходное изображение
            box: Координаты области
            field_name: Название поля
            custom_params: Дополнительные параметры
            
        Returns:
            Предобработанная область
        """
        # Получаем параметры для поля
        params = self.field_specific_params.get(field_name, {}).copy()
        if custom_params:
            params.update(custom_params)
        
        # Вырезаем область
        region = img.crop(box)
        
        # Масштабирование
        scale_factor = params.get('scale_factor', 3)
        if scale_factor > 1:
            width, height = region.size
            new_size = (int(width * scale_factor), int(height * scale_factor))
            region = region.resize(new_size, Image.LANCZOS)
        
        # Удаление линий (для ФИО в ФинУнив)
        if params.get('remove_lines', False) or params.get('aggressive_line_removal', False):
            processor = AdvancedImageProcessor()
            region = processor.remove_lines_horizontal(
                region, 
                aggressive=params.get('aggressive_line_removal', False)
            )
        
        # Улучшение параметров
        enhancement_params = {}
        if 'contrast_boost' in params:
            enhancement_params['contrast'] = params['contrast_boost']
        if 'brightness_boost' in params:
            enhancement_params['brightness'] = params['brightness_boost']
        if 'sharpness_boost' in params:
            enhancement_params['sharpness'] = params['sharpness_boost']
        
        if enhancement_params:
            processor = AdvancedImageProcessor()
            region = processor.enhance_image_advanced(region, enhancement_params)
        
        # Удаление шума
        noise_method = params.get('noise_reduction')
        if noise_method:
            processor = AdvancedImageProcessor()
            region = processor.remove_noise(region, noise_method)
        
        # Адаптивная бинаризация
        if params.get('adaptive_threshold', False):
            processor = AdvancedImageProcessor()
            region = processor.adaptive_threshold(region)
        
        logger.debug(f"Предобработка поля {field_name}: {params}")
        return region
    
    def create_field_thumbnail(self, img: Image.Image, box: Tuple[int, int, int, int],
                             target_size: Tuple[int, int] = (120, 80)) -> Image.Image:
        """
        Создание миниатюры поля для интерфейса
        
        Args:
            img: Исходное изображение
            box: Координаты поля
            target_size: Размер миниатюры
            
        Returns:
            Миниатюра поля
        """
        try:
            # Вырезаем с небольшим отступом
            processor = AdvancedImageProcessor()
            region = processor.crop_with_margin(img, box, margin=3)
            
            # Создаем миниатюру
            region.thumbnail(target_size, Image.LANCZOS)
            
            # Создаем изображение фиксированного размера с белым фоном
            thumbnail = Image.new('RGB', target_size, 'white')
            
            # Центрируем миниатюру
            x_offset = (target_size[0] - region.width) // 2
            y_offset = (target_size[1] - region.height) // 2
            thumbnail.paste(region, (x_offset, y_offset))
            
            return thumbnail
            
        except Exception as e:
            logger.error(f"Ошибка создания миниатюры: {e}")
            # Возвращаем заглушку
            return Image.new('RGB', target_size, 'lightgray')


# Утилитные функции для работы с изображениями
def pil_to_base64(img: Image.Image, format: str = 'PNG') -> str:
    """
    Конвертация PIL изображения в base64 строку
    
    Args:
        img: PIL изображение
        format: Формат ('PNG', 'JPEG')
        
    Returns:
        Base64 строка
    """
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str


def base64_to_pil(img_str: str) -> Image.Image:
    """
    Конвертация base64 строки в PIL изображение
    
    Args:
        img_str: Base64 строка
        
    Returns:
        PIL изображение
    """
    img_data = base64.b64decode(img_str)
    img = Image.open(io.BytesIO(img_data))
    return img


def save_debug_image(img: Image.Image, filename: str, debug_dir: str = 'debug_images') -> bool:
    """
    Сохранение изображения для отладки
    
    Args:
        img: Изображение для сохранения
        filename: Имя файла
        debug_dir: Директория для сохранения
        
    Returns:
        True если успешно сохранено
    """
    try:
        Path(debug_dir).mkdir(exist_ok=True)
        filepath = Path(debug_dir) / filename
        img.save(filepath)
        logger.debug(f"Отладочное изображение сохранено: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения отладочного изображения: {e}")
        return False


# Конфигурации для разных типов обработки
ENHANCEMENT_PRESETS = {
    'document_scan': {
        'contrast': 1.3,
        'sharpness': 1.2,
        'brightness': 1.05
    },
    'low_quality': {
        'contrast': 1.8,
        'sharpness': 1.5,
        'brightness': 1.2
    },
    'high_quality': {
        'contrast': 1.1,
        'sharpness': 1.05,
        'brightness': 1.0
    },
    'finuniv_certificate': {
        'contrast': 2.0,
        'sharpness': 1.6,
        'brightness': 1.3,
        'aggressive_line_removal': True
    }
}


def get_enhancement_preset(preset_name: str) -> Dict[str, float]:
    """
    Получение предустановки для улучшения изображения
    
    Args:
        preset_name: Название предустановки
        
    Returns:
        Словарь параметров улучшения
    """
    return ENHANCEMENT_PRESETS.get(preset_name, ENHANCEMENT_PRESETS['document_scan'])


# Инициализация при импорте
logger.info(f"ImageProcessor загружен. Доступные предустановки: {list(ENHANCEMENT_PRESETS.keys())}")