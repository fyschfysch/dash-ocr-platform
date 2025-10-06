"""
Конфигурации документов и парсеры для различных организаций
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Callable, Optional


class DocumentConfig:
    """
    Конфигурация для распознавания определенного типа документа
    """
    
    def __init__(self, name: str, organization: str, document_type: str,
                 fields: List[Dict[str, Any]], patterns: Dict[str, Callable],
                 ocr_params: Optional[Dict[str, Any]] = None):
        """
        Args:
            name: Название конфигурации
            organization: Организация-эмитент
            document_type: Тип документа
            fields: Список полей с координатами
            patterns: Парсеры для каждого поля
            ocr_params: Параметры OCR
        """
        self.name = name
        self.organization = organization
        self.document_type = document_type
        self.fields = fields
        self.patterns = patterns
        self.ocr_params = ocr_params or {}
        self.config_id = f"{organization}_{document_type}".upper()


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
        # Паттерн для даты
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
                    return result, False
                except ValueError:
                    pass
        
        return text.strip(), True


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
        text = re.sub(r'[^\w\s]', ' ', text.strip())
        
        # Паттерны для поиска серии и номера
        patterns = [
            r'(\d{2})\s+(\d{6,})',  # "02 123456"
            r'(\d{2})(\d{6,})',     # "02123456"
            r'(\d{2})\s(\d{6,})'    # "02 123456"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                series, number = match.group(1), match.group(2)[:6]
                uncertain = len(number) < 4
                return series, number, uncertain
        
        return "", "", True
    
    @staticmethod
    def parse_reg_number(text: str) -> Tuple[str, bool]:
        """
        Парсинг регистрационного номера
        """
        # Удаляем лишние символы
        cleaned_text = re.sub(r'[^\d]', '', text)
        digits = ''.join(re.findall(r'\d', cleaned_text))
        
        corrections_made = False
        
        # Специальная коррекция для частого OCR-сбоя
        if '000004' in digits and len(digits) == 6:
            if text.count('0') >= 3:
                corrections_made = True
        
        if len(digits) >= 6:
            # Берем первые 6 цифр или корректируем на основе паттерна "00XXXX"
            match_00 = re.search(r'00(\d{4})', digits)
            result = match_00.group(0) if match_00 else digits[:6]
            uncertain = len(digits) < 4 or corrections_made
            return result, uncertain
        
        return digits.zfill(6), True
    
    @staticmethod
    def parse_date_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты для удостоверений 1Т
        """
        return CommonParsers.parse_date_standard(text)
    
    @staticmethod
    def parse_date_diploma(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты для дипломов 1Т в формате "20.12.2024"
        """
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
        if match:
            day, month, year = match.groups()
            try:
                result = datetime(int(year), int(month), int(day)).date().isoformat()
                return result, False
            except ValueError:
                return text.strip(), True
        
        return text.strip(), True


class RosNouParsers:
    """
    Парсеры для документов РОСНОУ
    """
    
    @staticmethod
    def parse_series_number(text: str) -> Tuple[str, str, bool]:
        """
        Парсинг серии и номера в формате "12-А 2024 10"
        """
        digits = ''.join(re.findall(r'\d', text))
        corrections_made = False
        
        if len(digits) >= 10:
            series = digits[:2]
            number = digits[2:12] if len(digits) >= 12 else digits[2:10]
            
            # Коррекция для частых OCR-ошибок в серии
            if series in ['71', '11', '17']:
                series = '77'
                corrections_made = True
            
            uncertain = len(number) < 8 or corrections_made
            return series, number, uncertain
        
        return digits[:2].zfill(2) if len(digits) >= 2 else "00", \
               digits[2:] if len(digits) > 2 else "", True
    
    @staticmethod
    def parse_reg_number_diploma(text: str) -> Tuple[str, bool]:
        """
        Парсинг рег. номера диплома в формате "NNNNN-"
        """
        original_text = text.upper()
        corrections_made = False
        
        # Коррекции для частых OCR-ошибок
        bas_corrections = {
            'ВАС': 'БАС', 'В': '8', 'АС': '8', 'А': '4', 'О': '0'
        }
        
        text_upper = original_text
        for wrong, correct in bas_corrections.items():
            if wrong in text_upper:
                text_upper = text_upper.replace(wrong, correct)
                corrections_made = True
        
        # Поиск паттерна "NNNNN-"
        match = re.search(r'(\d{5})-', text_upper, re.UNICODE)
        if match:
            result = f"{match.group(1)}-"
            return result, corrections_made
        
        # Fallback: берем первые 5 цифр
        digits = re.findall(r'\d', text)
        if digits:
            result = f"{''.join(digits[:5]).zfill(5)}-"
            return result, True
        
        return "00000-", True
    
    @staticmethod
    def parse_reg_number_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсинг рег. номера удостоверения в формате "ПАД-243"
        """
        match = re.search(r'([А-Я]{2,3})-(\d{3})', text.upper(), re.IGNORECASE)
        if match:
            letters = match.group(1)
            corrections_made = False
            
            # Коррекция частых OCR-ошибок
            letter_corrections = {'РАД': 'ПАД', 'А': '4'}
            if letters in letter_corrections:
                letters = letter_corrections[letters]
                corrections_made = True
            
            return f"{letters}-{match.group(2)}", corrections_made
        
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
            return result, uncertain
        elif len(lines) == 1:
            result = lines[0].strip()
            uncertain = len(result) < 8
            return result, uncertain
        
        return text.strip(), True
    
    @staticmethod
    def parse_fullname_certificate(text: str) -> Tuple[str, bool]:
        """
        Парсинг ФИО для удостоверения
        """
        result = text.strip()
        return result, len(result) < 8


class FinUnivParsers:
    """
    Парсеры для документов Финансового университета
    """
    
    @staticmethod
    def parse_series_number_v1(text: str) -> Tuple[str, str, bool]:
        """
        Парсинг серии и номера v1 в формате "77 3301156696"
        """
        # Поиск серии из 2 цифр и номера из 8+ цифр
        match = re.search(r'(\d{2})\s+(\d{8,})', text.upper())
        if match:
            series = match.group(1)
            number = match.group(2)[:8]  # Берем первые 8 цифр
            uncertain = len(number) < 8
            return series, number, uncertain
        
        # Альтернативный паттерн без пробела
        match = re.search(r'(\d{2})(\d{8,})', text.upper())
        if match:
            series = match.group(1)
            number = match.group(2)[:8]
            uncertain = len(number) < 8
            return series, number, uncertain
        
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
            return result, len(result) < 5
        
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
        result = text.strip()
        return result, len(result) < 8
    
    @staticmethod
    def parse_fullname_complex(text: str) -> Tuple[str, bool]:
        """
        Сложный парсинг ФИО (вариант 2) с удалением подчеркиваний
        """
        # Удаляем подчеркивания и лишние символы
        cleaned_text = re.sub(r'_{2,}', ' ', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text.strip())
        
        # Паттерны для поиска ФИО
        patterns = [
            r'(\w+)\s+(\w+)\s+(\w+)',  # Фамилия Имя Отчество
            r'(\w+)\s+(\w+)',          # Фамилия Имя
            r'(\w+)'                   # Только фамилия
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                surname, name, patronymic = match.groups() if len(match.groups()) == 3 else (*match.groups(), "")
                
                # Убираем лишние дефисы в конце
                if surname.endswith('-'):
                    surname = surname[:-1]
                if name.endswith('-'):
                    name = name[:-1]
                if patronymic.endswith('-'):
                    patronymic = patronymic[:-1]
                
                result = f"{surname} {name} {patronymic}".strip()
                return result, True
        
        # TODO: В будущем можно добавить pymorphy2 для склонения
        result = cleaned_text.strip()
        return result, True
    
    @staticmethod
    def parse_date_from_text(text: str) -> Tuple[str, bool]:
        """
        Парсинг даты с поддержкой разных форматов
        """
        # Паттерны для дат
        date_patterns = [
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',      # "02 января 2024"
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',    # "02.01.2024"
            r'(\d{1,2})\s+(\w+)\s+(\d{4})\s*г\.?',  # "02 января 2024 г."
            r'(\d{1,2})/(\d{1,2})/(\d{4})'       # "02/01/2024"
        ]
        
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                day, month_str, year = match.groups()
                
                # Проверяем, является ли месяц названием или цифрой
                month = months.get(month_str.lower())
                if not month:
                    try:
                        month = int(month_str)
                    except ValueError:
                        continue
                
                try:
                    result = datetime(int(year), month, int(day)).date().isoformat()
                    return result, False
                except ValueError:
                    continue
        
        return text.strip(), True


class UncertaintyEngine:
    """
    Движок для оценки неуверенности в распознанных данных
    """
    
    def __init__(self, organization: str):
        """
        Args:
            organization: Название организации для настройки порогов
        """
        self.organization = organization
        
        # Пороги неуверенности для разных организаций
        self.thresholds = {
            '1T': {
                'min_reg_digits': 4,
                'min_name_length': 5,
                'min_number_length': 4
            },
            'ROSNOU': {
                'min_reg_digits': 3,
                'min_name_length': 8,
                'min_number_length': 6
            },
            'FINUNIVERSITY': {
                'min_reg_digits': 4,
                'min_name_length': 8,
                'min_number_length': 8
            }
        }
    
    def should_flag_uncertainty(self, field_name: str, original_text: str, 
                              parsed_result: Any, corrections_made: bool = False) -> bool:
        """
        Определяет, следует ли пометить поле как неуверенное
        
        Args:
            field_name: Название поля
            original_text: Исходный текст OCR
            parsed_result: Результат парсинга
            corrections_made: Были ли сделаны коррекции
            
        Returns:
            True если поле следует пометить как неуверенное
        """
        config = self.thresholds.get(self.organization, {})
        
        if corrections_made:
            return True
        
        if field_name == 'registrationnumber':
            digits_count = len(re.findall(r'\d', original_text))
            return digits_count < config.get('min_reg_digits', 3)
        
        elif field_name == 'fullname':
            return len(str(parsed_result).strip()) < config.get('min_name_length', 5)
        
        elif field_name == 'seriesandnumber':
            if isinstance(parsed_result, tuple) and len(parsed_result) == 2:
                number_length = len(str(parsed_result[1]))
                return number_length < config.get('min_number_length', 4)
        
        return False


# Конфигурации документов
DOCUMENT_CONFIGS = {
    # 1Т конфигурации
    '1T_CERTIFICATE': DocumentConfig(
        name="1Т Удостоверение",
        organization="1T",
        document_type="certificate",
        fields=[
            {'name': 'fullname', 'box': (630, 280, 1150, 320)},
            {'name': 'seriesandnumber', 'box': (207, 503, 380, 536)},
            {'name': 'registrationnumber', 'box': (320, 725, 425, 755)},
            {'name': 'issuedate', 'box': (150, 750, 440, 785)}
        ],
        patterns={
            'seriesandnumber': OneTParsers.parse_series_number,
            'registrationnumber': OneTParsers.parse_reg_number,
            'issuedate': OneTParsers.parse_date_certificate
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 1.5}
    ),
    
    '1T_DIPLOMA': DocumentConfig(
        name="1Т Диплом",
        organization="1T",
        document_type="diploma",
        fields=[
            {'name': 'fullname', 'box': (695, 262, 1120, 295)},
            {'name': 'seriesandnumber', 'box': (240, 535, 355, 570)},
            {'name': 'registrationnumber', 'box': (315, 725, 430, 760)},
            {'name': 'issuedate', 'box': (200, 570, 410, 600)}
        ],
        patterns={
            'seriesandnumber': OneTParsers.parse_series_number,
            'registrationnumber': OneTParsers.parse_reg_number,
            'issuedate': OneTParsers.parse_date_diploma
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 1.5}
    ),
    
    # РОСНОУ конфигурации
    'ROSNOU_DIPLOMA': DocumentConfig(
        name="РОСНОУ Диплом",
        organization="ROSNOU",
        document_type="diploma",
        fields=[
            {'name': 'fullname', 'box': (750, 130, 1030, 185)},
            {'name': 'seriesandnumber', 'box': (195, 385, 425, 415)},
            {'name': 'registrationnumber', 'box': (215, 585, 415, 620)},
            {'name': 'issuedate', 'box': (175, 700, 445, 730)}
        ],
        patterns={
            'fullname': RosNouParsers.parse_fullname_diploma,
            'seriesandnumber': RosNouParsers.parse_series_number,
            'registrationnumber': RosNouParsers.parse_reg_number_diploma,
            'issuedate': CommonParsers.parse_date_standard
        },
        ocr_params={'scale_factor': 6, 'contrast_boost': 2.5}
    ),
    
    'ROSNOU_CERTIFICATE': DocumentConfig(
        name="РОСНОУ Удостоверение",
        organization="ROSNOU",
        document_type="certificate",
        fields=[
            {'name': 'fullname', 'box': (700, 150, 1050, 190)},
            {'name': 'seriesandnumber', 'box': (215, 385, 445, 425)},
            {'name': 'registrationnumber', 'box': (260, 565, 411, 590)},
            {'name': 'issuedate', 'box': (230, 685, 420, 715)}
        ],
        patterns={
            'fullname': RosNouParsers.parse_fullname_certificate,
            'seriesandnumber': RosNouParsers.parse_series_number,
            'registrationnumber': RosNouParsers.parse_reg_number_certificate,
            'issuedate': CommonParsers.parse_date_standard
        },
        ocr_params={'scale_factor': 6, 'contrast_boost': 2.5}
    ),
    
    # Финуниверситет конфигурации
    'FINUNIV_CERT_V1': DocumentConfig(
        name="Финуниверситет Удостоверение (вариант 1)",
        organization="FINUNIVERSITY",
        document_type="certificate_v1",
        fields=[
            {'name': 'fullname', 'box': (645, 251, 995, 280)},
            {'name': 'seriesandnumber', 'box': (740, 175, 971, 210)},
            {'name': 'registrationnumber', 'box': (345, 650, 490, 678)},
            {'name': 'issuedate', 'box': (885, 320, 1085, 350)}
        ],
        patterns={
            'fullname': FinUnivParsers.parse_fullname_simple,
            'seriesandnumber': FinUnivParsers.parse_series_number_v1,
            'registrationnumber': FinUnivParsers.parse_reg_number_v1,
            'issuedate': FinUnivParsers.parse_date_from_text
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 2.0}
    ),
    
    'FINUNIV_CERT_V2': DocumentConfig(
        name="Финуниверситет Удостоверение (вариант 2 - дательный падеж)",
        organization="FINUNIVERSITY",
        document_type="certificate_v2",
        fields=[
            {'name': 'fullname', 'box': (826, 215, 1110, 320)},
            {'name': 'seriesandnumber', 'box': (762, 178, 990, 216)},
            {'name': 'registrationnumber', 'box': (370, 660, 475, 690)},
            {'name': 'issuedate', 'box': (930, 320, 1110, 365)}
        ],
        patterns={
            'fullname': FinUnivParsers.parse_fullname_complex,  # Сложный парсинг ФИО
            'seriesandnumber': FinUnivParsers.parse_series_number_v2,
            'registrationnumber': FinUnivParsers.parse_reg_number_v2,
            'issuedate': FinUnivParsers.parse_date_from_text
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 2.0, 'aggressive_line_removal': True}
    )
}


def get_available_configs() -> List[str]:
    """
    Возвращает список доступных конфигураций
    """
    return list(DOCUMENT_CONFIGS.keys())


def get_config(config_key: str) -> DocumentConfig:
    """
    Получение конфигурации по ключу
    """
    if config_key not in DOCUMENT_CONFIGS:
        available = list(DOCUMENT_CONFIGS.keys())
        raise ValueError(f"Конфигурация '{config_key}' не найдена. Доступные: {available}")
    
    return DOCUMENT_CONFIGS[config_key]


def get_field_description(field_name: str) -> str:
    """
    Возвращает описание поля для интерфейса
    """
    descriptions = {
        'fullname': 'ФИО (в именительном падеже)',
        'series': 'Серия документа',
        'number': 'Номер документа',
        'seriesandnumber': 'Серия и номер документа',
        'registrationnumber': 'Регистрационный номер',
        'issuedate': 'Дата выдачи (в ISO формате)'
    }
    
    return descriptions.get(field_name, field_name)