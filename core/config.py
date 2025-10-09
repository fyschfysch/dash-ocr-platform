"""
Конфигурации документов для OCR платформы
Содержит все настройки для поддерживаемых организаций и типов документов
"""

from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import re

# Импорты парсеров
from core.parsers import (
    CommonParsers, OneTParsers, RosNouParsers, FinUnivParsers,
    TextCleaner, OCRCorrector
)

logger = logging.getLogger(__name__)


@dataclass
class DocumentConfig:
    """
    Конфигурация документа для OCR
    """
    name: str
    organization: str
    document_type: str
    config_id: str
    fields: List[Dict[str, Any]]
    patterns: Dict[str, Callable]
    ocr_params: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        """Валидация после инициализации"""
        if not self.fields:
            raise ValueError(f"Конфигурация {self.name} должна содержать поля")
        
        for field in self.fields:
            if 'name' not in field:
                raise ValueError("Каждое поле должно иметь название")


class UncertaintyEngine:
    """
    Движок определения неуверенности в результатах OCR
    """
    
    def __init__(self, organization: str):
        self.organization = organization
        self.confidence_thresholds = {
            'fullname': 0.7,
            'seriesandnumber': 0.6,
            'registrationnumber': 0.5,
            'issuedate': 0.6
        }
        
        # Паттерны для выявления плохого OCR
        self.bad_ocr_patterns = [
            r'[^\w\s\.,\-№]',  # Странные символы
            r'^\s*$',          # Пустая строка
            r'^.{1,2}$',       # Слишком короткий текст
            r'[0O]{3,}',       # Много нулей подряд
            r'[lI1|]{3,}',     # Много похожих символов
        ]
        
        # Организационные особенности
        self.org_specific_rules = {
            '1T': self._check_1t_uncertainties,
            'ROSNOU': self._check_rosnou_uncertainties,
            'FINUNIV': self._check_finuniv_uncertainties
        }
        
        logger.debug(f"UncertaintyEngine создан для {organization}")
    
    def should_flag_uncertainty(self, field_name: str, raw_text: str, 
                              parsed_value: Any, parser_uncertainty: bool) -> bool:
        """
        Определяет, нужно ли помечать поле как неуверенное
        
        Args:
            field_name: Название поля
            raw_text: Исходный текст от OCR
            parsed_value: Обработанное значение
            parser_uncertainty: Неуверенность от парсера
            
        Returns:
            True если поле требует проверки
        """
        # Если парсер уже пометил как неуверенное
        if parser_uncertainty:
            return True
        
        # Проверяем паттерны плохого OCR
        if self._has_bad_ocr_patterns(raw_text):
            return True
        
        # Организационные правила
        org_check = self._get_org_checker()
        if org_check and org_check(field_name, raw_text, parsed_value):
            return True
        
        # Специфические проверки по типам полей
        if field_name == 'fullname':
            return self._check_fullname_uncertainty(raw_text, parsed_value)
        elif field_name == 'issuedate':
            return self._check_date_uncertainty(raw_text, parsed_value)
        elif field_name in ['series', 'number', 'seriesandnumber']:
            return self._check_series_number_uncertainty(raw_text, parsed_value)
        
        return False
    
    def _has_bad_ocr_patterns(self, text: str) -> bool:
        """Проверка на паттерны плохого OCR"""
        for pattern in self.bad_ocr_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _get_org_checker(self) -> Optional[Callable]:
        """Получение функции проверки для организации"""
        for org_key, checker in self.org_specific_rules.items():
            if org_key in self.organization.upper():
                return checker
        return None
    
    def _check_1t_uncertainties(self, field_name: str, raw_text: str, parsed_value: Any) -> bool:
        """Специфические проверки для 1Т"""
        if field_name == 'seriesandnumber':
            # Проверяем формат "02 123456"
            if not re.match(r'^\d{2}\s+\d{4,}', str(parsed_value)):
                return True
        
        elif field_name == 'registrationnumber':
            # Регномер 1Т обычно 6 цифр начинающихся с 00
            if not re.match(r'^00\d{4}$', str(parsed_value)):
                return True
        
        return False
    
    def _check_rosnou_uncertainties(self, field_name: str, raw_text: str, parsed_value: Any) -> bool:
        """Специфические проверки для РОСНОУ"""
        if field_name == 'seriesandnumber':
            # РОСНОУ имеет формат "ПБ 12345678" или "77-А 2024 123"
            series_number = str(parsed_value).upper()
            if not (re.match(r'^[А-Я]{2}\s+\d{8}', series_number) or 
                   re.match(r'^\d{2}-[А-Я]\s+\d{4}\s+\d+', series_number)):
                return True
        
        elif field_name == 'registrationnumber':
            # РОСНОУ регномер содержит буквы и цифры
            if not re.search(r'[А-Я]', str(parsed_value).upper()):
                return True
        
        return False
    
    def _check_finuniv_uncertainties(self, field_name: str, raw_text: str, parsed_value: Any) -> bool:
        """Специфические проверки для ФинУниверситета"""
        if field_name == 'fullname':
            # Проверяем, что ФИО не слишком короткое
            name_parts = str(parsed_value).split()
            if len(name_parts) < 2:  # Хотя бы имя и фамилия
                return True
            
            # Проверяем на наличие цифр (признак плохого OCR)
            if re.search(r'\d', str(parsed_value)):
                return True
        
        elif field_name == 'issuedate':
            # ФинУнив имеет специфический формат даты
            if not re.search(r'\d{1,2}.*\d{4}', str(parsed_value)):
                return True
        
        return False
    
    def _check_fullname_uncertainty(self, raw_text: str, parsed_value: str) -> bool:
        """Проверка неуверенности для ФИО"""
        if not parsed_value or len(parsed_value.strip()) < 5:
            return True
        
        # Проверяем, что есть хотя бы пробел (разделитель имен)
        if ' ' not in parsed_value.strip():
            return True
        
        # Проверяем на подозрительные символы
        if re.search(r'[^\w\s\-\.]', parsed_value):
            return True
        
        return False
    
    def _check_date_uncertainty(self, raw_text: str, parsed_value: str) -> bool:
        """Проверка неуверенности для даты"""
        if not parsed_value:
            return True
        
        # Проверяем наличие цифр года
        if not re.search(r'20\d{2}', parsed_value):
            return True
        
        return False
    
    def _check_series_number_uncertainty(self, raw_text: str, parsed_value: str) -> bool:
        """Проверка неуверенности для серии/номера"""
        if not parsed_value or len(parsed_value.strip()) < 3:
            return True
        
        return False


# Конфигурации документов
def create_1t_certificate_config() -> DocumentConfig:
    """Конфигурация для удостоверений 1Т"""
    return DocumentConfig(
        name="1Т - Удостоверение о повышении квалификации",
        organization="1T",
        document_type="certificate",
        config_id="1T_CERTIFICATE",
        description="Удостоверения 1Т с полями ФИО, серия/номер, рег.номер, дата",
        fields=[
            {
                'name': 'fullname',
                'display_name': 'ФИО',
                'box': (150, 200, 550, 250),  # Примерные координаты
                'required': True
            },
            {
                'name': 'seriesandnumber',
                'display_name': 'Серия и номер',
                'box': (400, 150, 600, 190),
                'required': True
            },
            {
                'name': 'registrationnumber',
                'display_name': 'Регистрационный номер',
                'box': (150, 450, 350, 490),
                'required': True
            },
            {
                'name': 'issuedate',
                'display_name': 'Дата выдачи',
                'box': (400, 450, 600, 490),
                'required': True
            }
        ],
        patterns={
            'fullname': CommonParsers.parse_fullname_simple,
            'seriesandnumber': OneTParsers.parse_series_number,
            'registrationnumber': OneTParsers.parse_reg_number,
            'issuedate': OneTParsers.parse_date_certificate
        },
        ocr_params={
            'scale_factor': 3,
            'contrast_boost': 1.5,
            'sharpness_boost': 1.2,
            'brightness_boost': 1.1,
            'denoise_method': 'bilateral'
        }
    )


def create_1t_diploma_config() -> DocumentConfig:
    """Конфигурация для дипломов 1Т"""
    return DocumentConfig(
        name="1Т - Диплом о профессиональной переподготовке",
        organization="1T",
        document_type="diploma",
        config_id="1T_DIPLOMA",
        description="Дипломы 1Т с расширенным набором полей",
        fields=[
            {
                'name': 'fullname',
                'display_name': 'ФИО',
                'box': (100, 180, 650, 230),  # Шире для диплома
                'required': True
            },
            {
                'name': 'seriesandnumber',
                'display_name': 'Серия и номер',
                'box': (450, 120, 650, 160),
                'required': True
            },
            {
                'name': 'registrationnumber',
                'display_name': 'Регистрационный номер',
                'box': (100, 500, 300, 540),
                'required': True
            },
            {
                'name': 'issuedate',
                'display_name': 'Дата выдачи',
                'box': (400, 500, 650, 540),
                'required': True
            }
        ],
        patterns={
            'fullname': CommonParsers.parse_fullname_simple,
            'seriesandnumber': OneTParsers.parse_series_number,
            'registrationnumber': OneTParsers.parse_reg_number,
            'issuedate': OneTParsers.parse_date_diploma
        },
        ocr_params={
            'scale_factor': 3,
            'contrast_boost': 1.4,
            'sharpness_boost': 1.3,
            'brightness_boost': 1.05
        }
    )


def create_rosnou_diploma_config() -> DocumentConfig:
    """Конфигурация для дипломов РОСНОУ"""
    return DocumentConfig(
        name="РОСНОУ - Диплом о профессиональной переподготовке",
        organization="ROSNOU",
        document_type="diploma",
        config_id="ROSNOU_DIPLOMA",
        description="Дипломы РОСНОУ с специфическими форматами серий",
        fields=[
            {
                'name': 'fullname',
                'display_name': 'ФИО',
                'box': (120, 200, 680, 250),
                'required': True
            },
            {
                'name': 'seriesandnumber',
                'display_name': 'Серия и номер',
                'box': (400, 140, 650, 180),
                'required': True
            },
            {
                'name': 'registrationnumber',
                'display_name': 'Регистрационный номер',
                'box': (120, 480, 350, 520),
                'required': True
            },
            {
                'name': 'issuedate',
                'display_name': 'Дата выдачи',
                'box': (400, 480, 650, 520),
                'required': True
            }
        ],
        patterns={
            'fullname': CommonParsers.parse_fullname_simple,
            'seriesandnumber': RosNouParsers.parse_series_number_diploma,
            'registrationnumber': RosNouParsers.parse_reg_number,
            'issuedate': CommonParsers.parse_date_standard
        },
        ocr_params={
            'scale_factor': 3,
            'contrast_boost': 1.6,
            'sharpness_boost': 1.1,
            'aggressive_line_removal': False
        }
    )


def create_rosnou_certificate_config() -> DocumentConfig:
    """Конфигурация для удостоверений РОСНОУ"""
    return DocumentConfig(
        name="РОСНОУ - Удостоверение о повышении квалификации",
        organization="ROSNOU",
        document_type="certificate",
        config_id="ROSNOU_CERTIFICATE",
        description="Удостоверения РОСНОУ с альтернативным форматом серий",
        fields=[
            {
                'name': 'fullname',
                'display_name': 'ФИО',
                'box': (150, 220, 600, 270),
                'required': True
            },
            {
                'name': 'seriesandnumber',
                'display_name': 'Серия и номер',
                'box': (380, 160, 580, 200),
                'required': True
            },
            {
                'name': 'registrationnumber',
                'display_name': 'Регистрационный номер',
                'box': (150, 460, 380, 500),
                'required': True
            },
            {
                'name': 'issuedate',
                'display_name': 'Дата выдачи',
                'box': (380, 460, 600, 500),
                'required': True
            }
        ],
        patterns={
            'fullname': CommonParsers.parse_fullname_simple,
            'seriesandnumber': RosNouParsers.parse_series_number_certificate,
            'registrationnumber': RosNouParsers.parse_reg_number,
            'issuedate': CommonParsers.parse_date_standard
        },
        ocr_params={
            'scale_factor': 3,
            'contrast_boost': 1.5,
            'sharpness_boost': 1.2
        }
    )


def create_finuniv_cert_v1_config() -> DocumentConfig:
    """Конфигурация для удостоверений ФинУниверситета v1 (ФИО в одну строку)"""
    return DocumentConfig(
        name="ФинУниверситет - Удостоверение (вариант 1)",
        organization="FINUNIV",
        document_type="certificate_v1",
        config_id="FINUNIV_CERT_V1",
        description="Удостоверения ФинУнив с ФИО в одну строку",
        fields=[
            {
                'name': 'fullname',
                'display_name': 'ФИО',
                'box': (180, 180, 620, 220),
                'required': True
            },
            {
                'name': 'seriesandnumber',
                'display_name': 'Серия и номер',
                'box': (420, 120, 620, 160),
                'required': True
            },
            {
                'name': 'registrationnumber',
                'display_name': 'Регистрационный номер',
                'box': (180, 440, 400, 480),
                'required': True
            },
            {
                'name': 'issuedate',
                'display_name': 'Дата выдачи',
                'box': (420, 440, 620, 480),
                'required': True
            }
        ],
        patterns={
            'fullname': FinUnivParsers.parse_fullname_single_line,
            'seriesandnumber': FinUnivParsers.parse_series_number,
            'registrationnumber': FinUnivParsers.parse_reg_number,
            'issuedate': FinUnivParsers.parse_date
        },
        ocr_params={
            'scale_factor': 4,
            'contrast_boost': 1.8,
            'sharpness_boost': 1.5,
            'brightness_boost': 1.2,
            'aggressive_line_removal': True,
            'denoise_method': 'bilateral'
        }
    )


def create_finuniv_cert_v2_config() -> DocumentConfig:
    """Конфигурация для удостоверений ФинУниверситета v2 (ФИО на трёх строках)"""
    return DocumentConfig(
        name="ФинУниверситет - Удостоверение (вариант 2)",
        organization="FINUNIV",
        document_type="certificate_v2",
        config_id="FINUNIV_CERT_V2",
        description="Удостоверения ФинУнив с многострочным ФИО в дательном падеже",
        fields=[
            {
                'name': 'fullname',
                'display_name': 'ФИО (дательный падеж)',
                'box': (180, 160, 620, 240),  # Выше область для 3 строк
                'required': True
            },
            {
                'name': 'seriesandnumber',
                'display_name': 'Серия и номер',
                'box': (420, 100, 620, 140),
                'required': True
            },
            {
                'name': 'registrationnumber',
                'display_name': 'Регистрационный номер',
                'box': (180, 460, 400, 500),
                'required': True
            },
            {
                'name': 'issuedate',
                'display_name': 'Дата выдачи',
                'box': (420, 460, 620, 520),  # Выше для многострочной даты
                'required': True
            }
        ],
        patterns={
            'fullname': FinUnivParsers.parse_fullname_multiline_dative,
            'seriesandnumber': FinUnivParsers.parse_series_number,
            'registrationnumber': FinUnivParsers.parse_reg_number,
            'issuedate': FinUnivParsers.parse_date_multiline
        },
        ocr_params={
            'scale_factor': 4,
            'contrast_boost': 2.0,
            'sharpness_boost': 1.6,
            'brightness_boost': 1.3,
            'aggressive_line_removal': True,
            'denoise_method': 'median'
        }
    )


# Реестр всех конфигураций
DOCUMENT_CONFIGS = {
    '1T_CERTIFICATE': create_1t_certificate_config,
    '1T_DIPLOMA': create_1t_diploma_config,
    'ROSNOU_DIPLOMA': create_rosnou_diploma_config,
    'ROSNOU_CERTIFICATE': create_rosnou_certificate_config,
    'FINUNIV_CERT_V1': create_finuniv_cert_v1_config,
    'FINUNIV_CERT_V2': create_finuniv_cert_v2_config
}


def get_available_configs() -> List[Dict[str, str]]:
    """
    Получение списка доступных конфигураций для UI
    
    Returns:
        Список словарей с информацией о конфигурациях
    """
    configs = []
    
    for config_id, config_func in DOCUMENT_CONFIGS.items():
        try:
            config = config_func()
            configs.append({
                'id': config_id,
                'name': config.name,
                'organization': config.organization,
                'document_type': config.document_type,
                'description': config.description or ''
            })
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации {config_id}: {e}")
    
    return sorted(configs, key=lambda x: (x['organization'], x['document_type']))


def get_config(config_id: str) -> DocumentConfig:
    """
    Получение конфигурации по ID
    
    Args:
        config_id: Идентификатор конфигурации
        
    Returns:
        Объект конфигурации документа
        
    Raises:
        ValueError: Если конфигурация не найдена
    """
    if config_id not in DOCUMENT_CONFIGS:
        available = ', '.join(DOCUMENT_CONFIGS.keys())
        raise ValueError(f"Конфигурация '{config_id}' не найдена. Доступные: {available}")
    
    try:
        config = DOCUMENT_CONFIGS[config_id]()
        logger.debug(f"Загружена конфигурация: {config.name}")
        return config
    except Exception as e:
        logger.error(f"Ошибка создания конфигурации {config_id}: {e}")
        raise


def get_configs_by_organization(organization: str) -> List[DocumentConfig]:
    """
    Получение всех конфигураций для организации
    
    Args:
        organization: Название организации
        
    Returns:
        Список конфигураций для организации
    """
    configs = []
    
    for config_id, config_func in DOCUMENT_CONFIGS.items():
        try:
            config = config_func()
            if organization.upper() in config.organization.upper():
                configs.append(config)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации {config_id}: {e}")
    
    return configs


def get_field_description(field_name: str) -> str:
    """
    Получение человекочитаемого описания поля
    
    Args:
        field_name: Внутреннее название поля
        
    Returns:
        Описание поля для пользователя
    """
    descriptions = {
        'fullname': 'ФИО',
        'series': 'Серия',
        'number': 'Номер',
        'seriesandnumber': 'Серия и номер',
        'registrationnumber': 'Регистрационный номер',
        'issuedate': 'Дата выдачи',
        'qualification': 'Квалификация',
        'speciality': 'Специальность',
        'hours': 'Количество часов',
        'period': 'Период обучения'
    }
    
    return descriptions.get(field_name, field_name.title())


def validate_config(config: DocumentConfig) -> List[str]:
    """
    Валидация конфигурации документа
    
    Args:
        config: Конфигурация для проверки
        
    Returns:
        Список ошибок валидации (пустой если всё в порядке)
    """
    errors = []
    
    # Проверяем обязательные поля
    if not config.name:
        errors.append("Отсутствует название конфигурации")
    
    if not config.organization:
        errors.append("Отсутствует название организации")
    
    if not config.fields:
        errors.append("Конфигурация должна содержать поля")
    
    # Проверяем поля
    for i, field in enumerate(config.fields):
        field_prefix = f"Поле {i+1}"
        
        if 'name' not in field:
            errors.append(f"{field_prefix}: отсутствует название поля")
        
        if 'box' in field and field['box']:
            box = field['box']
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                errors.append(f"{field_prefix}: координаты должны содержать 4 значения")
            elif not all(isinstance(x, (int, float)) for x in box):
                errors.append(f"{field_prefix}: координаты должны быть числами")
            elif box[2] <= box[0] or box[3] <= box[1]:
                errors.append(f"{field_prefix}: некорректные координаты (x2>x1, y2>y1)")
    
    # Проверяем парсеры
    for field in config.fields:
        field_name = field.get('name', '')
        if field_name in config.patterns:
            parser = config.patterns[field_name]
            if not callable(parser):
                errors.append(f"Парсер для поля '{field_name}' должен быть функцией")
    
    return errors


# Инициализация при импорте модуля
def _init_configs():
    """Инициализация и проверка всех конфигураций"""
    successful = 0
    failed = 0
    
    for config_id, config_func in DOCUMENT_CONFIGS.items():
        try:
            config = config_func()
            validation_errors = validate_config(config)
            
            if validation_errors:
                logger.warning(f"Конфигурация {config_id} имеет предупреждения: {validation_errors}")
            else:
                successful += 1
                logger.debug(f"Конфигурация {config_id} успешно загружена")
                
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка инициализации конфигурации {config_id}: {e}")
    
    logger.info(f"Инициализация конфигураций: {successful} успешно, {failed} ошибок")


# Запускаем инициализацию при импорте
_init_configs()