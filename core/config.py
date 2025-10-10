"""
Конфигурации документов с координатами полей
"""

from typing import List, Dict, Any, Callable, Optional
import re


class DocumentConfig:
    """Конфигурация документа с метаданными и параметрами OCR"""
    
    def __init__(self, name: str, organization: str, document_type: str,
                 fields: List[Dict[str, Any]], patterns: Dict[str, Callable],
                 ocr_params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.organization = organization
        self.document_type = document_type
        self.fields = fields
        self.patterns = patterns
        self.ocr_params = ocr_params or {}
        self.config_id = f"{organization}_{document_type}".upper()


class UncertaintyEngine:
    """Система оценки неуверенности распознавания"""
    
    def __init__(self, organization: str):
        self.organization = organization
        self.thresholds = {
            '1T': {
                'min_reg_digits': 4,
                'min_name_length': 5,
                'min_series_length': 2,
                'min_number_length': 4
            },
            'ROSNOU': {
                'min_reg_digits': 3,
                'min_name_length': 8,
                'min_series_length': 2,
                'min_number_length': 6
            },
            'FINUNIVERSITY': {
                'min_reg_digits': 4,
                'min_name_length': 8,
                'min_series_length': 2,
                'min_number_length': 8
            }
        }
    
    def should_flag_uncertainty(self, field_name: str, original_text: str,
                               parsed_result: Any, corrections_made: bool = False) -> bool:
        """Определяет, требует ли поле ручной проверки"""
        config = self.thresholds.get(self.organization, {})
        
        if corrections_made:
            return True
        
        if field_name == 'registration_number':
            digits_count = len(re.findall(r'\d', original_text))
            return digits_count < config.get('min_reg_digits', 3)
        
        elif field_name == 'full_name':
            return len(str(parsed_result).strip()) < config.get('min_name_length', 5)
        
        elif field_name == 'series':
            return len(str(parsed_result).strip()) < config.get('min_series_length', 2)
        
        elif field_name == 'number':
            return len(str(parsed_result).strip()) < config.get('min_number_length', 4)
        
        elif field_name == 'series_and_number':
            if isinstance(parsed_result, tuple) and len(parsed_result) >= 2:
                series_length = len(str(parsed_result[0]))
                number_length = len(str(parsed_result[1]))
                return (series_length < config.get('min_series_length', 2) or 
                       number_length < config.get('min_number_length', 4))
        
        return False


try:
    from core.parsers import (
        OneTParsers, RosNouParsers, FinUnivParsers, CommonParsers
    )
except ImportError:
    from parsers import (
        OneTParsers, RosNouParsers, FinUnivParsers, CommonParsers
    )


DOCUMENT_CONFIGS = {
    '1T_CERTIFICATE': DocumentConfig(
        name='Удостоверение 1Т о повышении квалификации',
        organization='1T',
        document_type='certificate',
        fields=[
            {'name': 'full_name', 'box': (630, 280, 1150, 320)},
            {'name': 'series', 'box': (207, 503, 270, 536)},
            {'name': 'number', 'box': (280, 503, 380, 536)},
            {'name': 'registration_number', 'box': (320, 725, 425, 755)},
            {'name': 'issue_date', 'box': (150, 750, 440, 785)}
        ],
        patterns={
            'series': OneTParsers.parse_series_only,
            'number': OneTParsers.parse_number_only,
            'registration_number': OneTParsers.parse_reg_number,
            'issue_date': OneTParsers.parse_date_certificate
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 1.5}
    ),
    
    '1T_DIPLOMA': DocumentConfig(
        name='Диплом 1Т о профессиональной переподготовке',
        organization='1T',
        document_type='diploma',
        fields=[
            {'name': 'full_name', 'box': (695, 262, 1120, 295)},
            {'name': 'series', 'box': (240, 535, 290, 570)},
            {'name': 'number', 'box': (295, 535, 355, 570)},
            {'name': 'registration_number', 'box': (315, 725, 430, 760)},
            {'name': 'issue_date', 'box': (200, 570, 410, 600)}
        ],
        patterns={
            'series': OneTParsers.parse_series_only,
            'number': OneTParsers.parse_number_only,
            'registration_number': OneTParsers.parse_reg_number,
            'issue_date': OneTParsers.parse_date_diploma
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 1.5}
    ),
    
    'ROSNOU_DIPLOMA': DocumentConfig(
        name='Диплом РОСНОУ о профессиональной переподготовке',
        organization='ROSNOU',
        document_type='diploma',
        fields=[
            {'name': 'full_name', 'box': (750, 130, 1030, 185)},
            {'name': 'series_and_number', 'box': (195, 385, 425, 415)},
            {'name': 'registration_number', 'box': (215, 585, 415, 620)},
            {'name': 'issue_date', 'box': (175, 700, 445, 730)}
        ],
        patterns={
            'full_name': RosNouParsers.parse_full_name_diploma,
            'series_and_number': RosNouParsers.parse_series_number,
            'registration_number': RosNouParsers.parse_reg_number_diploma,
            'issue_date': CommonParsers.parse_date_standard
        },
        ocr_params={'scale_factor': 6, 'contrast_boost': 2.5}
    ),
    
    'ROSNOU_CERTIFICATE': DocumentConfig(
        name='Удостоверение РОСНОУ о повышении квалификации',
        organization='ROSNOU',
        document_type='certificate',
        fields=[
            {'name': 'full_name', 'box': (700, 150, 1050, 190)},
            {'name': 'series_and_number', 'box': (215, 385, 445, 425)},
            {'name': 'registration_number', 'box': (260, 565, 411, 590)},
            {'name': 'issue_date', 'box': (230, 685, 420, 715)}
        ],
        patterns={
            'full_name': RosNouParsers.parse_full_name_certificate,
            'series_and_number': RosNouParsers.parse_series_number,
            'registration_number': RosNouParsers.parse_reg_number_certificate,
            'issue_date': CommonParsers.parse_date_standard
        },
        ocr_params={'scale_factor': 6, 'contrast_boost': 2.5}
    ),
    
    'FINUNIV_CERT_V1': DocumentConfig(
        name='Удостоверение Финансового университета (вариант 1)',
        organization='FINUNIVERSITY',
        document_type='certificate_v1',
        fields=[
            {'name': 'full_name', 'box': (645, 251, 995, 280)},
            {'name': 'series_and_number', 'box': (740, 175, 971, 210)},
            {'name': 'registration_number', 'box': (345, 650, 490, 678)},
            {'name': 'issue_date', 'box': (885, 320, 1085, 350)}
        ],
        patterns={
            'full_name': FinUnivParsers.parse_full_name_simple,
            'series_and_number': FinUnivParsers.parse_series_number_v1,
            'registration_number': FinUnivParsers.parse_reg_number_v1,
            'issue_date': FinUnivParsers.parse_date_from_text
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 2.0}
    ),
    
    'FINUNIV_CERT_V2': DocumentConfig(
        name='Удостоверение Финансового университета (вариант 2)',
        organization='FINUNIVERSITY',
        document_type='certificate_v2',
        fields=[
            {'name': 'full_name', 'box': (826, 215, 1110, 320)},
            {'name': 'series_and_number', 'box': (762, 178, 990, 216)},
            {'name': 'registration_number', 'box': (370, 660, 475, 690)},
            {'name': 'issue_date', 'box': (930, 320, 1110, 365)}
        ],
        patterns={
            'full_name': FinUnivParsers.parse_full_name_complex,
            'series_and_number': FinUnivParsers.parse_series_number_v2,
            'registration_number': FinUnivParsers.parse_reg_number_v2,
            'issue_date': FinUnivParsers.parse_date_from_text
        },
        ocr_params={'scale_factor': 4, 'contrast_boost': 2.0}
    )
}


def get_config(config_key: str) -> DocumentConfig:
    """Получение конфигурации по ключу"""
    if config_key not in DOCUMENT_CONFIGS:
        available = list(DOCUMENT_CONFIGS.keys())
        raise ValueError(f"Неподдерживаемый тип: {config_key}. Доступные: {available}")
    return DOCUMENT_CONFIGS[config_key]


def get_available_configs() -> List[Dict[str, str]]:
    """
    Получение списка доступных конфигураций для Dashboard
    
    Returns:
        List[Dict]: Список словарей с информацией о конфигурациях
    """
    configs = []
    for config_id, config in DOCUMENT_CONFIGS.items():
        configs.append({
            'id': config_id,
            'name': config.name,
            'organization': config.organization,
            'document_type': config.document_type
        })
    return configs


def get_field_description(field_name: str) -> str:
    """
    Получение описания поля для отображения в интерфейсе
    
    Args:
        field_name: Имя поля
        
    Returns:
        str: Человекочитаемое описание поля
    """
    descriptions = {
        'full_name': 'ФИО',
        'series': 'Серия',
        'number': 'Номер',
        'series_and_number': 'Серия и номер',
        'registration_number': 'Регистрационный номер',
        'issue_date': 'Дата выдачи'
    }
    return descriptions.get(field_name, field_name)
