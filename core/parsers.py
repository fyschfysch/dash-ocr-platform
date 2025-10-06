"""
Парсеры для различных организаций и типов полей документов
Содержит специализированные функции для обработки OCR-текста
"""

import re
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


class TextCleaner:
    """
    Утилиты для очистки и нормализации текста
    """
    
    @staticmethod
    def clean_digits_only(text: str) -> str:
        """Оставляет только цифры"""
        return ''.join(re.findall(r'\d', text))
    
    @staticmethod
    def clean_alphanumeric(text: str) -> str:
        """Оставляет только буквы и цифры"""
        return re.sub(r'[^\w\s]', ' ', text.strip())
    
    @staticmethod
    def normalize_spaces(text: str) -> str:
        """Нормализует пробелы"""
        return re.sub(r'\s+', ' ', text.strip())
    
    @staticmethod
    def remove_underscores(text: str) -> str:
        """Удаляет подчеркивания"""
        return re.sub(r'_{2,}', ' ', text)


class OCRCorrector:
    """
    Коррекция частых OCR-ошибок для разных организаций
    """
    
    # Общие коррекции цифр
    DIGIT_CORRECTIONS = {
        'О': '0', 'о': '0', 'O': '0',
        'l': '1', 'I': '1', '|': '1',
        'Z': '2', 'z': '2',
        'B': '8', 'В': '8',
        'S': '5', 's': '5',
        'G': '6', 'g': '6'
    }
    
    # Коррекции для РОСНОУ
    ROSNOU_CORRECTIONS = {
        'ВАС': 'БАС', 'В': '8', 'АС': '8', 'А': '4', 'О': '0',
        'РАД': 'ПАД'
    }
    
    # Коррекции серий для РОСНОУ
    ROSNOU_SERIES_CORRECTIONS = {
        '71': '77', '11': '77', '17': '77'
    }
    
    @classmethod
    def apply_digit_corrections(cls, text: str) -> Tuple[str, bool]:
        """Применяет коррекции цифр"""
        original_text = text
        corrected_text = text
        
        for wrong, correct in cls.DIGIT_CORRECTIONS.items():
            corrected_text = corrected_text.replace(wrong, correct)
        
        corrections_made = original_text != corrected_text
        return corrected_text, corrections_made
    
    @classmethod
    def apply_rosnou_corrections(cls, text: str) -> Tuple[str, bool]:
        """Применяет коррекции для РОСНОУ"""
        original_text = text.upper()
        corrected_text = original_text
        corrections_made = False
        
        for wrong, correct in cls.ROSNOU_CORRECTIONS.items():
            if wrong in corrected_text:
                corrected_text = corrected_text.replace(wrong, correct)
                corrections_made = True
                logger.debug(f"РОСНОУ коррекция: {wrong} → {correct}")
        
        return corrected_text, corrections_made


class CommonParsers:
    """
    Общие парсеры для всех организаций
    """
    
    @staticmethod
    def parse_date_standard(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты в формате "02 января 2024 г."
        
        Returns:
            Tuple[дата_в_ISO_формате, флаг_неуверенности]
        """
        # Паттерн для даты с названием месяца
        match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text, re.IGNORECASE)
        
        if match:
            day, month_str, year = match.groups()
            
            # Словарь месяцев
            months = {
                'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
            }
            
            month = months.get(month_str.lower())
            if month:
                try:
                    result = datetime(int(year), month, int(day)).date().isoformat()
                    logger.debug(f"Парсинг даты: '{text}' → '{result}'")
                    return result, False
                except ValueError:
                    logger.warning(f"Некорректная дата: {day}.{month}.{year}")
        
        return text.strip(), True
    
    @staticmethod
    def parse_date_numeric(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты в числовом формате "20.12.2024"
        """
        patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # 20.12.2024
            r'(\d{1,2})/(\d{1,2})/(\d{4})',   # 20/12/2024
            r'(\d{1,2})-(\d{1,2})-(\d{4})'    # 20-12-2024
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                day, month, year = match.groups()
                try:
                    result = datetime(int(year), int(month), int(day)).date().isoformat()
                    logger.debug(f"Парсинг числовой даты: '{text}' → '{result}'")
                    return result, False
                except ValueError:
                    continue
        
        return text.strip(), True
    
    @staticmethod
    def parse_fullname_simple(text: str) -> Tuple[str, bool]:
        """
        Простой парсинг ФИО
        """
        result = TextCleaner.normalize_spaces(text)
        uncertain = len(result) < 8
        return result, uncertain


class OneTParsers:
    """
    Парсеры для документов 1Т
    """
    
    @staticmethod
    def parse_series_number(text: str) -> Tuple[str, str, bool]:
        """
        Парсинг серии и номера в формате "02 123456"
        
        Returns:
            Tuple[серия, номер, флаг_неуверенности]
        """
        # Очистка текста
        cleaned_text = TextCleaner.clean_alphanumeric(text)
        
        # Применяем коррекции цифр
        corrected_text, corrections_made = OCRCorrector.apply_digit_corrections(cleaned_text)
        
        # Паттерны для поиска серии и номера
        patterns = [
            r'(\d{2})\s+(\d{6,})',  # "02 123456"
            r'(\d{2})(\d{6,})',     # "02123456"
            r'(\d{2})\s(\d{6,})'    # "02 123456"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, corrected_text)
            if match:
                series, number = match.group(1), match.group(2)[:6]  # Берем первые 6 цифр номера
                uncertain = len(number) < 4 or corrections_made
                
                logger.debug(f"1Т серия/номер: '{text}' → серия='{series}', номер='{number}'")
                return series, number, uncertain
        
        logger.warning(f"Не удалось распарсить серию/номер 1Т: '{text}'")
        return "", "", True
    
    @staticmethod
    def parse_reg_number(text: str) -> Tuple[str, bool]:
        """
        Парсинг регистрационного номера 1Т
        """
        # Удаляем лишние символы, оставляем только цифры
        digits = TextCleaner.clean_digits_only(text)
        corrections_made = False
        
        # Специальная коррекция для частого OCR-сбоя "000004"
        if '000004' in digits and len(digits) == 6:
            if text.count('0') >= 3:
                corrections_made = True
                logger.debug(f"1Т рег.номер коррекция '000004': '{text}'")
        
        if len(digits) >= 6:
            # Паттерн "00XXXX" - берем первые 6 цифр
            match_00 = re.search(r'00(\d{4})', digits)
            result = match_00.group(0) if match_00 else digits[:6]
            uncertain = len(digits) < 4 or corrections_made
            
            logger.debug(f"1Т рег.номер: '{text}' → '{result}'")
            return result, uncertain
        
        # Дополняем нулями до 6 цифр
        result = digits.zfill(6)
        logger.warning(f"1Т рег.номер дополнен нулями: '{text}' → '{result}'")
        return result, True
    
    @staticmethod
    def parse_date_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты для удостоверений 1Т (стандартный формат)
        """
        return CommonParsers.parse_date_standard(text)
    
    @staticmethod
    def parse_date_diploma(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты для дипломов 1Т (числовой формат)
        """
        return CommonParsers.parse_date_numeric(text)


class RosNouParsers:
    """
    Парсеры для документов РОСНОУ
    """
    
    @staticmethod
    def parse_series_number(text: str) -> Tuple[str, str, bool]:
        """
        Парсинг серии и номера в формате "12-А 2024 10"
        """
        digits = TextCleaner.clean_digits_only(text)
        corrections_made = False
        
        if len(digits) >= 10:
            series = digits[:2]
            number = digits[2:12] if len(digits) >= 12 else digits[2:10]
            
            # Коррекция для частых OCR-ошибок в серии
            if series in OCRCorrector.ROSNOU_SERIES_CORRECTIONS:
                original_series = series
                series = OCRCorrector.ROSNOU_SERIES_CORRECTIONS[series]
                corrections_made = True
                logger.debug(f"РОСНОУ серия коррекция: '{original_series}' → '{series}'")
            
            uncertain = len(number) < 8 or corrections_made
            logger.debug(f"РОСНОУ серия/номер: '{text}' → серия='{series}', номер='{number}'")
            return series, number, uncertain
        
        # Fallback для коротких номеров
        series = digits[:2].zfill(2) if len(digits) >= 2 else "00"
        number = digits[2:] if len(digits) > 2 else ""
        
        logger.warning(f"РОСНОУ короткий серия/номер: '{text}' → серия='{series}', номер='{number}'")
        return series, number, True
    
    @staticmethod
    def parse_reg_number_diploma(text: str) -> Tuple[str, bool]:
        """
        Парсинг рег. номера диплома в формате "NNNNN-"
        """
        original_text = text.upper()
        corrections_made = False
        
        # Применяем коррекции РОСНОУ
        corrected_text, corrections_made = OCRCorrector.apply_rosnou_corrections(original_text)
        
        # Поиск паттерна "NNNNN-"
        match = re.search(r'(\d{5})-', corrected_text, re.UNICODE)
        if match:
            result = f"{match.group(1)}-"
            logger.debug(f"РОСНОУ диплом рег.номер: '{text}' → '{result}'")
            return result, corrections_made
        
        # Fallback: берем первые 5 цифр и добавляем дефис
        digits = re.findall(r'\d', corrected_text)
        if digits:
            result = f"{''.join(digits[:5]).zfill(5)}-"
            logger.warning(f"РОСНОУ диплом рег.номер fallback: '{text}' → '{result}'")
            return result, True
        
        logger.error(f"РОСНОУ диплом рег.номер не найден: '{text}'")
        return "00000-", True
    
    @staticmethod
    def parse_reg_number_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсинг рег. номера удостоверения в формате "ПАД-243"
        """
        # Поиск паттерна "ААА-NNN"
        match = re.search(r'([А-Я]{2,3})-(\d{3})', text.upper(), re.IGNORECASE)
        if match:
            letters = match.group(1)
            corrections_made = False
            
            # Коррекция частых OCR-ошибок
            if letters == 'РАД':
                letters = 'ПАД'
                corrections_made = True
                logger.debug(f"РОСНОУ удост. коррекция: 'РАД' → 'ПАД'")
            
            result = f"{letters}-{match.group(2)}"
            logger.debug(f"РОСНОУ удост. рег.номер: '{text}' → '{result}'")
            return result, corrections_made
        
        logger.warning(f"РОСНОУ удост. рег.номер не найден: '{text}'")
        return "ПАД-000", True
    
    @staticmethod
    def parse_fullname_diploma(text: str) -> Tuple[str, bool]:
        """
        Парсинг ФИО для диплома (может быть на нескольких строках)
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if len(lines) >= 2:
            result = f"{lines[0]} {lines[1]}"
            uncertain = any(len(line) < 2 for line in lines[:2])
            logger.debug(f"РОСНОУ диплом ФИО (многострочное): '{result}'")
            return result, uncertain
        elif len(lines) == 1:
            result = lines[0].strip()
            uncertain = len(result) < 8
            logger.debug(f"РОСНОУ диплом ФИО (однострочное): '{result}'")
            return result, uncertain
        
        logger.warning(f"РОСНОУ диплом ФИО пустое: '{text}'")
        return text.strip(), True
    
    @staticmethod
    def parse_fullname_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсинг ФИО для удостоверения
        """
        result = TextCleaner.normalize_spaces(text)
        uncertain = len(result) < 8
        logger.debug(f"РОСНОУ удост. ФИО: '{result}'")
        return result, uncertain


class FinUnivParsers:
    """
    Парсеры для документов Финансового университета
    """
    
    @staticmethod
    def parse_series_number_v1(text: str) -> Tuple[str, str, bool]:
        """
        Парсинг серии и номера v1 в формате "77 3301156696"
        """
        # Применяем коррекции цифр
        corrected_text, corrections_made = OCRCorrector.apply_digit_corrections(text)
        
        # Поиск серии из 2 цифр и номера из 8+ цифр
        match = re.search(r'(\d{2})\s+(\d{8,})', corrected_text)
        if match:
            series = match.group(1)
            number = match.group(2)[:8]  # Берем первые 8 цифр
            uncertain = len(number) < 8 or corrections_made
            
            logger.debug(f"ФинУнив v1 серия/номер: '{text}' → серия='{series}', номер='{number}'")
            return series, number, uncertain
        
        # Альтернативный паттерн без пробела
        match = re.search(r'(\d{2})(\d{8,})', corrected_text)
        if match:
            series = match.group(1)
            number = match.group(2)[:8]
            uncertain = len(number) < 8 or corrections_made
            
            logger.debug(f"ФинУнив v1 серия/номер (без пробела): '{text}' → серия='{series}', номер='{number}'")
            return series, number, uncertain
        
        logger.warning(f"ФинУнив v1 серия/номер не найден: '{text}'")
        return "", "", True
    
    @staticmethod
    def parse_series_number_v2(text: str) -> Tuple[str, str, bool]:
        """
        Парсинг серии и номера v2 (аналогично v1)
        """
        return FinUnivParsers.parse_series_number_v1(text)
    
    @staticmethod
    def parse_reg_number_v1(text: str) -> Tuple[str, bool]:
        """
        Парсинг рег. номера v1 в формате "06.11373"
        """
        match = re.search(r'(\d+\.\d+)', text, re.IGNORECASE)
        if match:
            result = match.group(1)
            uncertain = len(result) < 5
            logger.debug(f"ФинУнив v1 рег.номер: '{text}' → '{result}'")
            return result, uncertain
        
        logger.warning(f"ФинУнив v1 рег.номер не найден: '{text}'")
        return text.strip(), True
    
    @staticmethod
    def parse_reg_number_v2(text: str) -> Tuple[str, bool]:
        """
        Парсинг рег. номера v2 (аналогично v1)
        """
        return FinUnivParsers.parse_reg_number_v1(text)
    
    @staticmethod
    def parse_fullname_simple(text: str) -> Tuple[str, bool]:
        """
        Простой парсинг ФИО (вариант 1)
        """
        return CommonParsers.parse_fullname_simple(text)
    
    @staticmethod
    def parse_fullname_complex(text: str) -> Tuple[str, bool]:
        """
        Сложный парсинг ФИО (вариант 2) с удалением подчеркиваний
        """
        # Удаляем подчеркивания и нормализуем пробелы
        cleaned_text = TextCleaner.remove_underscores(text)
        cleaned_text = TextCleaner.normalize_spaces(cleaned_text)
        
        # Паттерны для поиска ФИО
        patterns = [
            r'(\w+)\s+(\w+)\s+(\w+)',  # Фамилия Имя Отчество
            r'(\w+)\s+(\w+)',          # Фамилия Имя
            r'(\w+)'                   # Только фамилия
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                parts = [part for part in match.groups() if part]
                
                # Убираем дефисы в конце каждой части
                cleaned_parts = []
                for part in parts:
                    if part.endswith('-'):
                        part = part[:-1]
                    cleaned_parts.append(part)
                
                result = ' '.join(cleaned_parts).strip()
                
                # Помечаем как неуверенное, так как может быть в дательном падеже
                logger.debug(f"ФинУнив v2 ФИО (сложное): '{text}' → '{result}' (требует проверки падежа)")
                return result, True
        
        # Fallback - возвращаем очищенный текст
        result = cleaned_text.strip()
        logger.warning(f"ФинУнив v2 ФИО fallback: '{text}' → '{result}'")
        return result, True
    
    @staticmethod
    def parse_date_from_text(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты с поддержкой разных форматов
        """
        # Сначала пробуем стандартный формат с названием месяца
        result, uncertain = CommonParsers.parse_date_standard(text)
        if not uncertain:
            return result, uncertain
        
        # Затем пробуем числовые форматы
        return CommonParsers.parse_date_numeric(text)


class ParserRegistry:
    """
    Реестр всех доступных парсеров
    """
    
    PARSERS = {
        # Общие парсеры
        'parse_date_standard': CommonParsers.parse_date_standard,
        'parse_date_numeric': CommonParsers.parse_date_numeric,
        'parse_fullname_simple': CommonParsers.parse_fullname_simple,
        
        # 1Т парсеры
        'parse_1t_series_number': OneTParsers.parse_series_number,
        'parse_1t_reg_number': OneTParsers.parse_reg_number,
        'parse_1t_date_certificate': OneTParsers.parse_date_certificate,
        'parse_1t_date_diploma': OneTParsers.parse_date_diploma,
        
        # РОСНОУ парсеры
        'parse_rosnou_series_number': RosNouParsers.parse_series_number,
        'parse_rosnou_reg_number_diploma': RosNouParsers.parse_reg_number_diploma,
        'parse_rosnou_reg_number_certificate': RosNouParsers.parse_reg_number_certificate,
        'parse_rosnou_fullname_diploma': RosNouParsers.parse_fullname_diploma,
        'parse_rosnou_fullname_certificate': RosNouParsers.parse_fullname_certificate,
        
        # ФинУнив парсеры
        'parse_finuniv_series_number_v1': FinUnivParsers.parse_series_number_v1,
        'parse_finuniv_series_number_v2': FinUnivParsers.parse_series_number_v2,
        'parse_finuniv_reg_number_v1': FinUnivParsers.parse_reg_number_v1,
        'parse_finuniv_reg_number_v2': FinUnivParsers.parse_reg_number_v2,
        'parse_finuniv_fullname_simple': FinUnivParsers.parse_fullname_simple,
        'parse_finuniv_fullname_complex': FinUnivParsers.parse_fullname_complex,
        'parse_finuniv_date': FinUnivParsers.parse_date_from_text
    }
    
    @classmethod
    def get_parser(cls, parser_name: str):
        """
        Получение парсера по имени
        """
        if parser_name not in cls.PARSERS:
            available = list(cls.PARSERS.keys())
            raise ValueError(f"Парсер '{parser_name}' не найден. Доступные: {available}")
        
        return cls.PARSERS[parser_name]
    
    @classmethod
    def list_parsers(cls) -> List[str]:
        """
        Список всех доступных парсеров
        """
        return list(cls.PARSERS.keys())


# Дополнительные утилиты для отладки
class ParserDebugger:
    """
    Утилиты для отладки парсеров
    """
    
    @staticmethod
    def test_parser(parser_func, test_cases: List[Tuple[str, Any]]) -> Dict[str, Any]:
        """
        Тестирование парсера на наборе тестовых случаев
        
        Args:
            parser_func: Функция парсера
            test_cases: Список кортежей (входной_текст, ожидаемый_результат)
            
        Returns:
            Словарь с результатами тестирования
        """
        results = {
            'total': len(test_cases),
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        for i, (input_text, expected) in enumerate(test_cases):
            try:
                actual = parser_func(input_text)
                passed = actual == expected
                
                results['details'].append({
                    'case': i + 1,
                    'input': input_text,
                    'expected': expected,
                    'actual': actual,
                    'passed': passed
                })
                
                if passed:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                results['details'].append({
                    'case': i + 1,
                    'input': input_text,
                    'expected': expected,
                    'actual': f"ERROR: {e}",
                    'passed': False
                })
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def benchmark_parser(parser_func, input_text: str, iterations: int = 1000) -> Dict[str, float]:
        """
        Бенчмарк производительности парсера
        """
        import time
        
        start_time = time.time()
        for _ in range(iterations):
            parser_func(input_text)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time = total_time / iterations
        
        return {
            'total_time': total_time,
            'average_time': avg_time,
            'iterations': iterations,
            'calls_per_second': iterations / total_time
        }
