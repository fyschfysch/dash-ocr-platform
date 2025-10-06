"""
Модуль для обработки изображений с использованием PIL и OpenCV
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageOps
import fitz  # PyMuPDF
import io
import os
from typing import List, Tuple, Dict, Optional, Any, Union
import logging

logger = logging.getLogger(__name__)


class AdvancedImageProcessor:
    """
    Продвинутый процессор изображений с множественными алгоритмами улучшения
    """
    
    def __init__(self, max_dimension: int = 1200, dpi: int = 300):
        """
        Args:
            max_dimension: Максимальный размер изображения по большей стороне
            dpi: DPI для конвертации PDF
        """
        self.max_dimension = max_dimension
        self.dpi = dpi
        
        # Предустановленные фильтры
        self.noise_removal_kernel = np.ones((1, 1), np.uint8)
        self.dilation_kernel = np.ones((1, 1), np.uint8)
        self.erosion_kernel = np.ones((1, 1), np.uint8)
    
    def convert_pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """
        Конвертация PDF в список изображений с высоким качеством
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Список PIL изображений
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")
        
        images = []
        
        try:
            pdf_document = fitz.open(pdf_path)
            logger.info(f"Открыт PDF: {pdf_path}, страниц: {len(pdf_document)}")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Матрица масштабирования для высокого качества
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Конвертация в PIL
                img_data = pix.tobytes("ppm")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
                
                logger.debug(f"Страница {page_num + 1}: {img.size}")
            
            pdf_document.close()
            logger.info(f"PDF успешно конвертирован: {len(images)} изображений")
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF: {e}")
            raise
        
        return images
    
    def convert_pdf_from_bytes(self, pdf_bytes: bytes) -> List[Image.Image]:
        """
        Конвертация PDF из байтов в список изображений
        
        Args:
            pdf_bytes: PDF в виде байтов
            
        Returns:
            Список PIL изображений
        """
        images = []
        
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            logger.info(f"PDF из байтов открыт, страниц: {len(pdf_document)}")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Высококачественная матрица
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Конвертация в PIL
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
                
                logger.debug(f"Страница {page_num + 1}: {img.size}")
            
            pdf_document.close()
            logger.info(f"PDF из байтов успешно конвертирован: {len(images)} изображений")
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF из байтов: {e}")
            raise
        
        return images
    
    def resize_image(self, img: Image.Image, max_dimension: Optional[int] = None) -> Image.Image:
        """
        Изменение размера изображения с сохранением пропорций
        
        Args:
            img: Исходное изображение
            max_dimension: Максимальный размер (по умолчанию self.max_dimension)
            
        Returns:
            Изображение с измененным размером
        """
        if max_dimension is None:
            max_dimension = self.max_dimension
        
        width, height = img.size
        max_dim = max(width, height)
        
        if max_dim > max_dimension:
            scale = max_dimension / max_dim
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # Используем LANCZOS для лучшего качества
            img_resized = img.resize((new_width, new_height), Image.LANCZOS)
            logger.debug(f"Изображение изменено: {width}x{height} → {new_width}x{new_height}")
            return img_resized
        
        return img
    
    def enhance_image_basic(self, img: Image.Image) -> Image.Image:
        """
        Базовые улучшения изображения с помощью PIL
        
        Args:
            img: Исходное изображение
            
        Returns:
            Улучшенное изображение
        """
        # Увеличение контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        
        # Увеличение резкости
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.1)
        
        # Коррекция яркости для темных изображений
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.05)
        
        logger.debug("Применены базовые улучшения изображения")
        return img
    
    def enhance_image_advanced(self, img: Image.Image) -> Image.Image:
        """
        Продвинутые улучшения изображения с помощью OpenCV
        
        Args:
            img: Исходное изображение PIL
            
        Returns:
            Улучшенное изображение PIL
        """
        # Конвертация PIL → OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Конвертация в градации серого
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Адаптивная гистограммная эквализация (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Гауссово размытие для уменьшения шума
        blurred = cv2.GaussianBlur(enhanced, (1, 1), 0)
        
        # Конвертация обратно в PIL
        result = Image.fromarray(blurred)
        if result.mode != 'RGB':
            result = result.convert('RGB')
        
        logger.debug("Применены продвинутые улучшения изображения")
        return result
    
    def rotate_image(self, img: Image.Image, rotation_angle: int) -> Image.Image:
        """
        Поворот изображения на указанный угол
        
        Args:
            img: Исходное изображение
            rotation_angle: Угол поворота (0, 90, 180, 270)
            
        Returns:
            Повернутое изображение
        """
        if rotation_angle == 90:
            result = img.transpose(Image.ROTATE_90)
        elif rotation_angle == 180:
            result = img.transpose(Image.ROTATE_180)
        elif rotation_angle == 270:
            result = img.transpose(Image.ROTATE_270)
        else:
            result = img
        
        if rotation_angle != 0:
            logger.debug(f"Изображение повернуто на {rotation_angle}°")
        
        return result
    
    def remove_lines_horizontal(self, img: Image.Image, aggressive: bool = False) -> Image.Image:
        """
        Удаление горизонтальных линий с помощью OpenCV
        Особенно полезно для документов ФинУниверситета
        
        Args:
            img: Исходное изображение PIL
            aggressive: Агрессивное удаление линий
            
        Returns:
            Изображение без горизонтальных линий
        """
        # Конвертация PIL → OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        if aggressive:
            # Агрессивное удаление линий
            # Создаем ядро для обнаружения горизонтальных линий
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            
            # Обнаруживаем горизонтальные линии
            lines_mask = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
            
            # Удаляем линии
            gray_no_lines = cv2.subtract(gray, lines_mask)
            
            # Усиливаем контраст
            gray_no_lines = cv2.addWeighted(gray_no_lines, 1.5, gray_no_lines, 0, 0)
            
            logger.debug("Применено агрессивное удаление горизонтальных линий")
        else:
            # Мягкое удаление шума
            gray_no_lines = cv2.bilateralFilter(gray, 9, 75, 75)
            logger.debug("Применен билатеральный фильтр")
        
        # Конвертация обратно в PIL
        result = Image.fromarray(gray_no_lines)
        if result.mode != 'RGB':
            result = result.convert('RGB')
        
        return result
    
    def remove_lines_vertical(self, img: Image.Image) -> Image.Image:
        """
        Удаление вертикальных линий
        """
        # Конвертация PIL → OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Создаем ядро для обнаружения вертикальных линий
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        
        # Обнаруживаем вертикальные линии
        lines_mask = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel)
        
        # Удаляем линии
        gray_no_lines = cv2.subtract(gray, lines_mask)
        
        # Конвертация обратно в PIL
        result = Image.fromarray(gray_no_lines)
        if result.mode != 'RGB':
            result = result.convert('RGB')
        
        logger.debug("Удалены вертикальные линии")
        return result
    
    def denoise_image(self, img: Image.Image, method: str = 'bilateral') -> Image.Image:
        """
        Удаление шума с изображения различными методами
        
        Args:
            img: Исходное изображение
            method: Метод ('bilateral', 'gaussian', 'median', 'morphological')
            
        Returns:
            Изображение без шума
        """
        # Конвертация PIL → OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        if method == 'bilateral':
            # Билатеральный фильтр - сохраняет края
            denoised = cv2.bilateralFilter(img_cv, 9, 75, 75)
        elif method == 'gaussian':
            # Гауссово размытие
            denoised = cv2.GaussianBlur(img_cv, (5, 5), 0)
        elif method == 'median':
            # Медианный фильтр
            denoised = cv2.medianBlur(img_cv, 5)
        elif method == 'morphological':
            # Морфологическое закрытие
            kernel = np.ones((3, 3), np.uint8)
            denoised = cv2.morphologyEx(img_cv, cv2.MORPH_CLOSE, kernel)
        else:
            denoised = img_cv
        
        # Конвертация обратно в PIL
        result = Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))
        
        logger.debug(f"Применен метод удаления шума: {method}")
        return result
    
    def adaptive_threshold(self, img: Image.Image, method: str = 'gaussian') -> Image.Image:
        """
        Адаптивная бинаризация изображения
        
        Args:
            img: Исходное изображение
            method: Метод ('gaussian', 'mean')
            
        Returns:
            Бинаризованное изображение
        """
        # Конвертация PIL → OpenCV → Grayscale
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        if method == 'gaussian':
            # Адаптивная пороговая обработка с Гауссовым взвешиванием
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            # Адаптивная пороговая обработка со средним значением
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2
            )
        
        # Конвертация обратно в PIL
        result = Image.fromarray(thresh)
        if result.mode != 'RGB':
            result = result.convert('RGB')
        
        logger.debug(f"Применена адаптивная бинаризация: {method}")
        return result
    
    def skew_correction(self, img: Image.Image) -> Image.Image:
        """
        Коррекция наклона изображения
        """
        # Конвертация PIL → OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Определение углов с помощью Hough Transform
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is not None:
            # Вычисляем средний угол наклона
            angles = []
            for rho, theta in lines[:10]:  # Берем первые 10 линий
                angle = theta * 180 / np.pi
                if angle > 90:
                    angle = angle - 180
                angles.append(angle)
            
            if angles:
                avg_angle = np.mean(angles)
                
                # Поворачиваем изображение для коррекции наклона
                if abs(avg_angle) > 0.5:  # Порог для коррекции
                    height, width = gray.shape
                    center = (width // 2, height // 2)
                    rotation_matrix = cv2.getRotationMatrix2D(center, avg_angle, 1.0)
                    corrected = cv2.warpAffine(img_cv, rotation_matrix, (width, height), 
                                             flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                    
                    result = Image.fromarray(cv2.cvtColor(corrected, cv2.COLOR_BGR2RGB))
                    logger.debug(f"Скорректирован наклон на {avg_angle:.2f}°")
                    return result
        
        return img
    
    def crop_to_content(self, img: Image.Image, margin: int = 20) -> Image.Image:
        """
        Обрезка изображения до содержимого (удаление белых полей)
        
        Args:
            img: Исходное изображение
            margin: Отступ от обнаруженного содержимого
            
        Returns:
            Обрезанное изображение
        """
        # Конвертация в градации серого
        gray = img.convert('L')
        
        # Инвертируем для поиска содержимого
        inverted = ImageOps.invert(gray)
        
        # Находим bounding box содержимого
        bbox = inverted.getbbox()
        
        if bbox:
            # Добавляем отступы
            left = max(0, bbox[0] - margin)
            top = max(0, bbox[1] - margin)
            right = min(img.width, bbox[2] + margin)
            bottom = min(img.height, bbox[3] + margin)
            
            cropped = img.crop((left, top, right, bottom))
            logger.debug(f"Изображение обрезано: {img.size} → {cropped.size}")
            return cropped
        
        return img


class RegionProcessor:
    """
    Специализированный процессор для обработки отдельных областей изображения
    """
    
    def __init__(self):
        self.base_processor = AdvancedImageProcessor()
    
    def preprocess_region_for_field(self, img: Image.Image, box: Tuple[int, int, int, int],
                                  field_name: str, params: Dict[str, Any]) -> Image.Image:
        """
        Предобработка области изображения для конкретного типа поля
        
        Args:
            img: Исходное изображение
            box: Координаты области (x1, y1, x2, y2)
            field_name: Тип поля
            params: Параметры обработки
            
        Returns:
            Обработанная область
        """
        # Вырезаем область
        region = img.crop(box)
        
        # Масштабирование
        scale_factor = params.get('scale_factor', 3)
        if scale_factor > 1:
            width, height = region.size
            new_size = (int(width * scale_factor), int(height * scale_factor))
            region = region.resize(new_size, Image.LANCZOS)
        
        # Улучшение контраста
        contrast_boost = params.get('contrast_boost', 1.5)
        if contrast_boost != 1.0:
            enhancer = ImageEnhance.Contrast(region)
            region = enhancer.enhance(contrast_boost)
        
        # Улучшение резкости
        sharpness_boost = params.get('sharpness_boost', 1.5)
        if sharpness_boost != 1.0:
            enhancer = ImageEnhance.Sharpness(region)
            region = enhancer.enhance(sharpness_boost)
        
        # Коррекция яркости
        brightness_boost = params.get('brightness_boost', 1.1)
        if brightness_boost != 1.0:
            enhancer = ImageEnhance.Brightness(region)
            region = enhancer.enhance(brightness_boost)
        
        # Специальная обработка для разных типов полей
        if field_name == 'fullname' and params.get('aggressive_line_removal'):
            region = self.base_processor.remove_lines_horizontal(region, aggressive=True)
        
        if params.get('denoise_method'):
            region = self.base_processor.denoise_image(region, params['denoise_method'])
        
        if params.get('adaptive_threshold'):
            region = self.base_processor.adaptive_threshold(region)
        
        # Применение медианного фильтра для устранения мелкого шума
        region = region.filter(ImageFilter.MedianFilter(size=3))
        
        # Конвертация в градации серого для OCR
        region = region.convert('L')
        
        logger.debug(f"Область {field_name} обработана: масштаб x{scale_factor}, контраст x{contrast_boost}")
        return region
    
    def extract_text_regions(self, img: Image.Image, 
                           min_area: int = 100) -> List[Tuple[int, int, int, int]]:
        """
        Автоматическое обнаружение текстовых областей на изображении
        
        Args:
            img: Исходное изображение
            min_area: Минимальная площадь области
            
        Returns:
            Список координат обнаруженных областей
        """
        # Конвертация PIL → OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Применяем адаптивную пороговую обработку
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Находим контуры
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Фильтруем контуры по площади и находим bounding boxes
        text_regions = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(contour)
                text_regions.append((x, y, x + w, y + h))
        
        logger.debug(f"Обнаружено {len(text_regions)} текстовых областей")
        return text_regions


class ImageAnalyzer:
    """
    Анализатор качества изображений для OCR
    """
    
    @staticmethod
    def analyze_image_quality(img: Image.Image) -> Dict[str, Any]:
        """
        Анализ качества изображения для OCR
        
        Args:
            img: Изображение для анализа
            
        Returns:
            Словарь с метриками качества
        """
        # Конвертация в OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Размер изображения
        height, width = gray.shape
        total_pixels = height * width
        
        # Оценка резкости (Laplacian variance)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Оценка контраста (стандартное отклонение)
        contrast = gray.std()
        
        # Оценка яркости (среднее значение)
        brightness = gray.mean()
        
        # Оценка шума (отношение высоких частот)
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = np.log(np.abs(f_shift) + 1)
        noise_level = magnitude_spectrum.std()
        
        # Детекция размытия
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        is_blurry = blur_score < 100
        
        # Оценка наклона (приблизительная)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        skew_angle = 0
        if lines is not None:
            angles = []
            for rho, theta in lines[:5]:
                angle = theta * 180 / np.pi
                if angle > 90:
                    angle = angle - 180
                angles.append(angle)
            if angles:
                skew_angle = np.mean(angles)
        
        return {
            'width': width,
            'height': height,
            'total_pixels': total_pixels,
            'sharpness': float(sharpness),
            'contrast': float(contrast),
            'brightness': float(brightness),
            'noise_level': float(noise_level),
            'blur_score': float(blur_score),
            'is_blurry': is_blurry,
            'skew_angle': float(skew_angle),
            'quality_score': ImageAnalyzer._calculate_quality_score(
                sharpness, contrast, brightness, noise_level, blur_score
            )
        }
    
    @staticmethod
    def _calculate_quality_score(sharpness: float, contrast: float, 
                               brightness: float, noise_level: float, 
                               blur_score: float) -> float:
        """
        Вычисление общей оценки качества изображения
        """
        # Нормализация параметров
        sharpness_norm = min(sharpness / 500, 1.0)  # Чем больше, тем лучше
        contrast_norm = min(contrast / 50, 1.0)     # Чем больше, тем лучше
        brightness_norm = 1.0 - abs(brightness - 127) / 127  # Оптимум около 127
        noise_norm = max(0, 1.0 - noise_level / 10)  # Чем меньше, тем лучше
        blur_norm = min(blur_score / 500, 1.0)      # Чем больше, тем лучше
        
        # Взвешенная сумма
        quality_score = (
            sharpness_norm * 0.25 +
            contrast_norm * 0.2 +
            brightness_norm * 0.2 +
            noise_norm * 0.15 +
            blur_norm * 0.2
        )
        
        return float(quality_score)
    
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
        
        if analysis['is_blurry']:
            suggestions.append("Изображение размыто - используйте повышение резкости")
        
        if analysis['contrast'] < 30:
            suggestions.append("Низкий контраст - увеличьте контрастность")
        
        if analysis['brightness'] < 100:
            suggestions.append("Изображение темное - увеличьте яркость")
        elif analysis['brightness'] > 180:
            suggestions.append("Изображение слишком яркое - уменьшите яркость")
        
        if abs(analysis['skew_angle']) > 2:
            suggestions.append(f"Изображение наклонено на {analysis['skew_angle']:.1f}° - примените коррекцию наклона")
        
        if analysis['noise_level'] > 8:
            suggestions.append("Высокий уровень шума - используйте шумоподавление")
        
        if analysis['total_pixels'] < 500000:  # Меньше 0.5 мегапикселя
            suggestions.append("Низкое разрешение - увеличьте размер изображения")
        
        if analysis['quality_score'] < 0.5:
            suggestions.append("Общее качество низкое - рассмотрите пересканирование документа")
        
        return suggestions


# Обратная совместимость с существующим кодом
class ImageProcessor(AdvancedImageProcessor):
    """
    Упрощенный интерфейс для обратной совместимости
    """
    
    def __init__(self, max_dimension: int = 1200, dpi: int = 300):
        super().__init__(max_dimension, dpi)
    
    def enhance_image(self, img: Image.Image) -> Image.Image:
        """Базовые улучшения (для совместимости)"""
        return self.enhance_image_basic(img)
    
    def remove_lines_from_region(self, img: Image.Image, aggressive: bool = False) -> Image.Image:
        """Удаление линий (для совместимости)"""
        return self.remove_lines_horizontal(img, aggressive)
