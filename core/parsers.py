"""
Парсеры для извлечения и обработки полей документов
Содержит специализированные парсеры для каждой организации
"""

import re
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TextCleaner:
    """
    Утилиты для очистки и нормализации текста после OCR
    """
    
    @staticmethod
    def clean_ocr_artifacts(text: str) -> str:
        """Удаление артефактов OCR"""
        if not text:
            return ""
        
        # Замены частых ошибок OCR
        ocr_corrections = {
            # Цифры и буквы
            'О': '0',  # Русская О на ноль
            'о': '0',  # Русская о на ноль
            'З': '3',  # Русская З на тройку
            'б': '6',  # Русская б на шестерку
            'Б': '6',  # Русская Б на шестерку
            'С': 'C',  # Русская С на английскую C
            'Р': 'P',  # Русская Р на английскую P
            'Н': 'H',  # Русская Н на английскую H
            'К': 'K',  # Русская К на английскую K
            'Х': 'X',  # Русская Х на английскую X
            'А': 'A',  # Русская А на английскую A
            'В': 'B',  # Русская В на английскую B
            'Е': 'E',  # Русская Е на английскую E
            'М': 'M',  # Русская М на английскую M
            'Т': 'T',  # Русская Т на английскую T
            'У': 'Y',  # Русская У на английскую Y
            
            # Специальные символы
            '|': 'I',
            '1': 'I',
            'l': 'I',
            '0': 'O'
        }
        
        cleaned = text
        for wrong, correct in ocr_corrections.items():
            cleaned = cleaned.replace(wrong, correct)
        
        return cleaned
    
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Нормализация пробелов"""
        if not text:
            return ""
        
        # Убираем лишние пробелы и переносы
        return ' '.join(text.split())
    
    @staticmethod
    def remove_punctuation_artifacts(text: str) -> str:
        """Удаление артефактов пунктуации"""
        if not text:
            return ""
        
        # Убираем лишние точки, запятые в неподходящих местах
        text = re.sub(r'[.,]{2,}', '.', text)
        text = re.sub(r'\s+[.,]\s+', ' ', text)
        
        return text.strip()


class OCRCorrector:
    """
    Корректор для исправления типичных ошибок OCR
    """
    
    # Словари исправлений для разных организаций
    COMMON_CORRECTIONS = {
        # Частые ошибки в сериях
        'ПО': 'ПБ',
        'П0': 'ПБ',
        'П8': 'ПБ',
        'Р0': 'РБ',
        'РО': 'РБ',
        
        # Ошибки в регистрационных номерах
        'О': '0',
        'о': '0',
        'З': '3',
        'Б': '6',
        'б': '6'
    }
    
    @staticmethod
    def correct_series_ocr(text: str, organization: str = '') -> str:
        """Коррекция ошибок в сериях документов"""
        corrected = text.upper()
        
        # Применяем общие исправления
        for wrong, correct in OCRCorrector.COMMON_CORRECTIONS.items():
            corrected = corrected.replace(wrong, correct)
        
        # Специфические исправления для организаций
        if 'ROSNOU' in organization.upper():
            # РОСНОУ специфические исправления
            rosnou_corrections = {
                'BAC': 'ВАК',
                '8AC': 'ВАК',
                'BAK': 'ВАК',
                'БAC': 'ВАК',
                'БАС': 'ВАК'
            }
            
            for wrong, correct in rosnou_corrections.items():
                corrected = corrected.replace(wrong, correct)
        
        return corrected


class CommonParsers:
    """
    Общие парсеры для всех типов документов
    """
    
    @staticmethod
    def parse_date_standard(text: str) -> Tuple[str, bool]:
        """
        Стандартный парсер даты в формате DD.MM.YYYY или DD MM YYYY
        
        Args:
            text: Исходный текст с датой
            
        Returns:
            Tuple[дата в ISO формате, флаг неуверенности]
        """
        if not text:
            return '', True
        
        # Паттерны для разных форматов дат
        date_patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # DD.MM.YYYY
            r'(\d{1,2})\s+(\d{1,2})\s+(\d{4})',  # DD MM YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{4})',  # DD-MM-YYYY
            r'(\d{1,2})/(\d{1,2})/(\d{4})'  # DD/MM/YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                day, month, year = match.groups()
                try:
                    # Валидируем дату
                    date_obj = datetime(int(year), int(month), int(day))
                    iso_date = date_obj.date().isoformat()
                    
                    logger.debug(f"Дата распознана: {text} -> {iso_date}")
                    return iso_date, False
                    
                except ValueError:
                    logger.warning(f"Некорректная дата: {day}.{month}.{year}")
                    continue
        
        return text.strip(), True
    
    @staticmethod
    def parse_fullname_simple(text: str) -> Tuple[str, bool]:
        """
        Простой парсер ФИО без падежных преобразований
        
        Args:
            text: Исходный текст с ФИО
            
        Returns:
            Tuple[очищенное ФИО, флаг неуверенности]
        """
        if not text:
            return '', True
        
        # Базовая очистка
        cleaned = TextCleaner.normalize_whitespace(text)
        cleaned = TextCleaner.remove_punctuation_artifacts(cleaned)
        
        # Проверяем минимальную длину и наличие пробелов
        uncertain = len(cleaned) < 5 or ' ' not in cleaned
        
        return cleaned, uncertain


class OneTParsers:
    """
    Парсеры для документов организации 1Т
    """
    
    @staticmethod
    def parse_series_number(text: str) -> Tuple[str, str, bool]:
        """
        Парсер серии и номера для документов 1Т
        Формат: "02 123456"
        
        Args:
            text: Исходный текст
            
        Returns:
            Tuple[серия, номер, флаг неуверенности]
        """
        if not text:
            return '', '', True
        
        # Очищаем текст от лишних символов
        cleaned = re.sub(r'[^\w\s]', ' ', text.strip())
        cleaned = ' '.join(cleaned.split())
        
        # Паттерны для серии и номера 1Т
        patterns = [
            r'(\d{2})\s+(\d{6,})',  # "02 123456"
            r'(\d{2})(\d{6,})',     # "02123456" (слитно)
            r'([А-Я]{2})\s+(\d{6,})'  # "АБ 123456" (буквенная серия)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                series, number = match.group(1), match.group(2)
                
                # Проверяем длину номера (должен быть минимум 4 цифры)
                uncertain = len(number) < 4
                
                logger.debug(f"1Т серия/номер: {text} -> {series} / {number}")
                return series, number, uncertain
        
        return '', '', True
    
    @staticmethod
    def parse_reg_number(text: str) -> Tuple[str, bool]:
        """
        Парсер регистрационного номера 1Т
        Формат: "000004" (6 цифр, обычно начинается с 00)
        
        Args:
            text: Исходный текст
            
        Returns:
            Tuple[регистрационный номер, флаг неуверенности]
        """
        if not text:
            return '', True
        
        # Извлекаем только цифры
        cleaned_text = re.sub(r'[^\d]', '', text)
        digits = ''.join(re.findall(r'\d', cleaned_text))
        
        corrections_made = False
        
        # Специфическая коррекция для 1Т
        # Часто встречается "000004" как базовый номер
        if "000004" in digits and len(digits) >= 6:
            # Проверяем на избыток нулей (артефакт OCR)
            if text.count('0') > 3:
                corrections_made = True
                logger.debug(f"Исправлено избыточное количество нулей: {text}")
        
        if len(digits) >= 6:
            # Берем первые 6 цифр для формата 1Т (00XXXX)
            result = digits[:6]
        else:
            # Дополняем нулями до 6 цифр
            result = digits.zfill(6)
        
        uncertain = len(digits) < 4 or corrections_made
        
        return result, uncertain
    
    @staticmethod
    def parse_date_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсер даты для удостоверений 1Т (стандартный формат)
        """
        return CommonParsers.parse_date_standard(text)
    
    @staticmethod
    def parse_date_diploma(text: str) -> Tuple[str, bool]:
        """
        Парсер даты для дипломов 1Т
        Формат: "20.12.2024"
        """
        if not text:
            return '', True
        
        # Специфический паттерн для дипломов 1Т
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
        if match:
            day, month, year = match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                result = date_obj.date().isoformat()
                return result, False
            except ValueError:
                return text.strip(), True
        
        return text.strip(), True


class RosNouParsers:
    """
    Парсеры для документов РОСНОУ
    """
    
    @staticmethod
    def parse_series_number_diploma(text: str) -> Tuple[str, str, bool]:
        """
        Парсер серии и номера для дипломов РОСНОУ
        Формат: "ПБ 12345678"
        """
        return RosNouParsers._parse_series_number_common(text, is_diploma=True)
    
    @staticmethod
    def parse_series_number_certificate(text: str) -> Tuple[str, str, bool]:
        """
        Парсер серии и номера для удостоверений РОСНОУ
        Формат: "77-А 2024 123"
        """
        return RosNouParsers._parse_series_number_common(text, is_diploma=False)
    
    @staticmethod
    def _parse_series_number_common(text: str, is_diploma: bool = True) -> Tuple[str, str, bool]:
        """
        Общий парсер серий РОСНОУ
        """
        if not text:
            return '', '', True
        
        # Извлекаем цифры
        digits = ''.join(re.findall(r'\d', text))
        corrections_made = False
        
        if is_diploma:
            # Для дипломов: формат "ПБ 12345678"
            if len(digits) >= 10:
                series = digits[:2]
                number = digits[2:10] if len(digits) >= 12 else digits[2:]
            else:
                series = digits[:2].zfill(2) if len(digits) >= 2 else '00'
                number = digits[2:] if len(digits) > 2 else ''
            
            # Коррекция серий
            if series in ['71', '11', '17']:
                series = '77'
                corrections_made = True
                logger.debug(f"Исправлена серия РОСНОУ: {digits[:2]} -> 77")
            
            uncertain = len(number) < 8 or corrections_made
            
        else:
            # Для удостоверений: формат "77-А 2024 123"
            # Ищем паттерн с буквой
            match = re.search(r'(\d{2})-?([А-Я])-?(\d{2,4})-?(\d+)', text.upper(), re.IGNORECASE)
            if match:
                prefix, letter, year, number = match.groups()
                series = f"{prefix}-{letter}"
                number = f"{year} {number}"
                uncertain = len(number) < 6
            else:
                series = digits[:2].zfill(2) if len(digits) >= 2 else '00'
                number = digits[2:] if len(digits) > 2 else ''
                uncertain = True
        
        return series, number, uncertain
    
    @staticmethod
    def parse_reg_number(text: str) -> Tuple[str, bool]:
        """
        Парсер регистрационного номера РОСНОУ
        Формат: "12345-А" для дипломов или "АБВ-123" для удостоверений
        """
        if not text:
            return '', True
        
        original_text = text.upper()
        corrections_made = False
        
        # Коррекция частых ошибок OCR для РОСНОУ
        bac_corrections = {
            'BAC': 'БАС',
            '8AC': 'БАС',
            'BAK': 'БАС',
            'БAC': 'БАС'
        }
        
        text_upper = original_text
        for wrong, correct in bac_corrections.items():
            if wrong in text_upper:
                text_upper = text_upper.replace(wrong, correct)
                corrections_made = True
                logger.debug(f"Исправлена ошибка OCR: {wrong} -> {correct}")
        
        # Паттерн для номера с дефисом: "12345-А"
        match = re.search(r'(\d{5})-([А-Я])', text_upper, re.UNICODE)
        if match:
            result = f"{match.group(1)}-{match.group(2)}"
            return result, corrections_made
        
        # Если не найден стандартный формат, собираем из цифр
        digits = re.findall(r'\d', text)
        if digits:
            result = f"{''.join(digits[:5]).zfill(5)}-А"
            logger.debug(f"Восстановлен регномер РОСНОУ: {result}")
            return result, True
        
        return "00000-А", True
    
    @staticmethod
    def parse_fullname_diploma(text: str) -> Tuple[str, bool]:
        """
        Парсер ФИО для дипломов РОСНОУ (может быть многострочным)
        """
        if not text:
            return '', True
        
        # Разбиваем на строки и очищаем
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if len(lines) >= 2:
            # Объединяем первые две строки
            result = f"{lines[0]} {lines[1]}"
            # Проверяем на короткие фрагменты
            uncertain = any(len(line) < 2 for line in lines[:2])
            return result, uncertain
        
        elif len(lines) == 1:
            result = lines[0].strip()
            uncertain = len(result) < 8
            return result, uncertain
        
        return text.strip(), True
    
    @staticmethod
    def parse_fullname_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсер ФИО для удостоверений РОСНОУ (обычно одна строка)
        """
        result = text.strip()
        return result, len(result) < 8


class FinUnivParsers:
    """
    Парсеры для документов Финансового университета
    """
    
    @staticmethod
    def parse_series_number(text: str) -> Tuple[str, str, bool]:
        """
        Парсер серии и номера для документов ФинУнив
        Формат v1: "77 3301156696"
        Формат v2: аналогичный
        """
        if not text:
            return '', '', True
        
        # Очищаем текст
        cleaned = OCRCorrector.correct_series_ocr(text, 'FINUNIV')
        
        # Паттерн для ФинУнив: "77 3301156696"
        match = re.search(r'(\d{2})\s*(\d{8,})', cleaned)
        if match:
            series = match.group(1)
            number = match.group(2)
            uncertain = len(number) < 8
            return series, number, uncertain
        
        # Альтернативный паттерн: "АБ 12345678"
        match = re.search(r'([А-Я]{2})\s*(\d{8,})', cleaned.upper())
        if match:
            series = match.group(1)
            number = match.group(2)
            uncertain = len(number) < 8
            return series, number, uncertain
        
        return '', '', True
    
    @staticmethod
    def parse_reg_number(text: str) -> Tuple[str, bool]:
        """
        Парсер регистрационного номера ФинУнив
        Формат: "06.11373"
        """
        if not text:
            return '', True
        
        # Паттерн для регномера ФинУнив: "NN.NNNNN"
        match = re.search(r'(\d{2})\.(\d{4,5})', text, re.IGNORECASE)
        if match:
            result = f"{match.group(1)}.{match.group(2)}"
            return result, len(result) < 5
        
        return text.strip(), True
    
    @staticmethod
    def parse_fullname_single_line(text: str) -> Tuple[str, bool]:
        """
        Парсер ФИО для ФинУнив v1 (одна строка)
        """
        if not text:
            return '', True
        
        result = TextCleaner.normalize_whitespace(text)
        uncertain = len(result) < 8
        
        return result, uncertain
    
    @staticmethod
    def parse_fullname_multiline_dative(text: str) -> Tuple[str, bool]:
        """
        Парсер ФИО для ФинУнив v2 (многострочное, в дательном падеже)
        Преобразует из дательного падежа в именительный
        """
        if not text:
            return '', True
        
        # Очищаем от артефактов OCR
        cleaned_text = re.sub(r'[-—]{2,}', '', text)
        cleaned_text = re.sub(r'\n+', ' ', cleaned_text.strip())
        
        # Паттерны для извлечения ФИО из дательного падежа
        patterns = [
            r'(\w+у?)\s+(\w+у?)\s+(\w+у?)',  # Фамилия Имя Отчество
            r'(\w+)\s+(\w+)\s+(\w+)',       # Стандартный паттерн
            r'(\w+)\s+(\w+)'                # Только имя и фамилия
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                parts = match.groups()
                
                # Базовое преобразование из дательного падежа
                converted_parts = []
                for part in parts:
                    if part.endswith('у'):
                        part = part[:-1]  # Убираем окончание 'у'
                    if part.endswith('е'):
                        part = part[:-1]  # Убираем окончание 'е'
                    converted_parts.append(part)
                
                result = ' '.join(converted_parts)
                logger.debug(f"Преобразование ФИО ФинУнив: {text.strip()} -> {result}")
                return result, True  # Помечаем как неуверенное из-за падежного преобразования
        
        # TODO: Интеграция с pymorphy2 для точного преобразования падежей
        result = cleaned_text.strip()
        logger.debug(f"Не удалось преобразовать падеж, возвращаем как есть: {result}")
        return result, True
    
    @staticmethod
    def parse_date(text: str) -> Tuple[str, bool]:
        """
        Парсер даты для ФинУнив (стандартный формат)
        """
        return FinUnivParsers.parse_date_multiline(text)
    
    @staticmethod
    def parse_date_multiline(text: str) -> Tuple[str, bool]:
        """
        Парсер даты для ФинУнив (может быть многострочной)
        Форматы: "30 мая 2024 г.", "30.05.2024"
        """
        if not text:
            return '', True
        
        # Словарь месяцев
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4,
            'май': 5, 'июн': 6, 'июл': 7, 'авг': 8,
            'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }
        
        # Различные паттерны дат для ФинУнив
        date_patterns = [
            # Паттерн типа "30 мая 2024 г."
            r'(\d{1,2})\s+([а-я]+)\s+(\d{4})',
            # Стандартные форматы
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'(\d{1,2})\s+(\d{1,2})\s+(\d{4})',
            r'(\d{1,2})-(\d{1,2})-(\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                day, month_str, year = match.groups()
                
                # Если месяц словом, преобразуем в номер
                if month_str.lower() in months:
                    month = months[month_str.lower()]
                else:
                    try:
                        month = int(month_str)
                    except ValueError:
                        continue
                
                try:
                    date_obj = datetime(int(year), month, int(day))
                    result = date_obj.date().isoformat()
                    logger.debug(f"ФинУнив дата: {text.strip()} -> {result}")
                    return result, False
                except ValueError:
                    continue
        
        return text.strip(), True


class ParserRegistry:
    """
    Реестр всех парсеров для удобного доступа
    """
    
    # Маппинг организаций к их парсерам
    ORGANIZATION_PARSERS = {
        '1T': OneTParsers,
        'ROSNOU': RosNouParsers,
        'FINUNIV': FinUnivParsers
    }
    
    @classmethod
    def get_parser_for_organization(cls, organization: str):
        """
        Получение парсера для организации
        
        Args:
            organization: Название организации
            
        Returns:
            Класс парсера или None
        """
        org_upper = organization.upper()
        for org_key, parser_class in cls.ORGANIZATION_PARSERS.items():
            if org_key in org_upper:
                return parser_class
        return None
    
    @classmethod
    def list_parsers(cls) -> List[str]:
        """
        Получение списка доступных парсеров
        
        Returns:
            Список названий организаций с парсерами
        """
        return list(cls.ORGANIZATION_PARSERS.keys())
    
    @classmethod
    def get_parser_methods(cls, organization: str) -> List[str]:
        """
        Получение списка методов парсера для организации
        
        Args:
            organization: Название организации
            
        Returns:
            Список названий методов парсера
        """
        parser_class = cls.get_parser_for_organization(organization)
        if not parser_class:
            return []
        
        # Получаем все статические методы класса
        methods = []
        for attr_name in dir(parser_class):
            attr = getattr(parser_class, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                methods.append(attr_name)
        
        return methods


# Вспомогательные функции для тестирования парсеров
def test_parser(parser_func, test_cases: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """
    Тестирование парсера на наборе тестовых случаев
    
    Args:
        parser_func: Функция парсера для тестирования
        test_cases: Список кортежей (входные_данные, ожидаемый_результат)
        
    Returns:
        Статистика тестирования
    """
    results = {
        'total': len(test_cases),
        'passed': 0,
        'failed': 0,
        'failures': []
    }
    
    for i, (input_text, expected) in enumerate(test_cases):
        try:
            actual = parser_func(input_text)
            if actual == expected:
                results['passed'] += 1
            else:
                results['failed'] += 1
                results['failures'].append({
                    'case': i,
                    'input': input_text,
                    'expected': expected,
                    'actual': actual
                })
        except Exception as e:
            results['failed'] += 1
            results['failures'].append({
                'case': i,
                'input': input_text,
                'expected': expected,
                'error': str(e)
            })
    
    return results


def validate_all_parsers():
    """
    Валидация всех парсеров в реестре
    """
    validation_results = {}
    
    for org, parser_class in ParserRegistry.ORGANIZATION_PARSERS.items():
        org_results = {}
        
        # Получаем все методы парсера
        methods = ParserRegistry.get_parser_methods(org)
        
        for method_name in methods:
            method = getattr(parser_class, method_name)
            org_results[method_name] = {
                'exists': callable(method),
                'is_static': isinstance(method, staticmethod) or not hasattr(method, '__self__')
            }
        
        validation_results[org] = org_results
    
    return validation_results


# Инициализация и логирование при импорте
logger.info(f"Загружены парсеры для организаций: {', '.join(ParserRegistry.ORGANIZATION_PARSERS.keys())}")