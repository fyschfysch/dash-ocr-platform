"""
Парсеры для извлечения полей из OCR текста
"""

from typing import Tuple
from datetime import datetime
import re


class CommonParsers:
    """Общие паттерны парсинга для всех типов документов"""
    
    @staticmethod
    def parse_date_standard(text: str) -> Tuple[str, bool]:
        """Парсинг стандартной даты в формате '02 декабря 2024 г.'"""
        match = re.search(r'(\d{1,2})\s+([а-яё]+)\s+(\d{4})', text, re.IGNORECASE)
        if match:
            day, month_str, year = match.groups()
            months = {
                'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
                'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
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
    """Паттерны парсинга для документов 1Т"""
    
    @staticmethod
    def parse_series_number(text: str) -> Tuple[str, str, bool]:
        """Парсинг серии и номера в формате '02 № 123456'"""
        text = re.sub(r'\s+', ' ', text.strip())
        patterns = [
            r'(\d{2})\s*№\s*(\d{6,})',
            r'(\d{2})\s+(\d{6,})',
            r'(\d{2})(\d{6,})'
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
        """Парсинг регистрационных номеров с обработкой перечеркиваний"""
        cleaned_text = re.sub(r'[_\-=~—–]+', '', text)
        digits = ''.join(re.findall(r'\d', cleaned_text))
        
        corrections_made = False
        
        if '000004' in digits and len(digits) == 6:
            if text.count('0') > 3:
                corrections_made = True
        
        if len(digits) >= 6:
            match_00 = re.search(r'00\d{4}', digits)
            result = match_00.group(0) if match_00 else digits[:6]
            uncertain = len(digits) < 4 or corrections_made
            return result, uncertain
        
        return digits.zfill(6), True
    
    @staticmethod
    def parse_date_certificate(text: str) -> Tuple[str, bool]:
        """Парсинг даты для удостоверения 1Т"""
        return CommonParsers.parse_date_standard(text)
    
    @staticmethod
    def parse_date_diploma(text: str) -> Tuple[str, bool]:
        """Парсинг даты для диплома 1Т в формате 'Выдан 20.12.2024 года'"""
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
    """Паттерны парсинга для документов РОСНОУ"""
    
    @staticmethod
    def parse_series_number(text: str) -> Tuple[str, str, bool]:
        """Парсинг 12-значного номера: серия (2 цифры) + номер (10 цифр)"""
        digits = ''.join(re.findall(r'\d', text))
        corrections_made = False
        
        if len(digits) >= 10:
            series = digits[:2]
            number = digits[2:12] if len(digits) >= 12 else digits[2:10]
            
            if series in ['71', '11', '17']:
                series = '77'
                corrections_made = True
            
            uncertain = len(number) < 8 or corrections_made
            return series, number, uncertain
        
        return digits[:2].zfill(2) if len(digits) >= 2 else "00", digits[2:] if len(digits) > 2 else "", True
    
    @staticmethod
    def parse_reg_number_diploma(text: str) -> Tuple[str, bool]:
        """Парсинг регистрационного номера в формате 'NNNNN-БАС'"""
        original_text = text.upper()
        corrections_made = False
        
        bas_corrections = {
            'BAC': 'БАС', 'ВАС': 'БАС', '8АС': 'БАС', 'БAC': 'БАС',
            'БА8': 'БАС', 'БАО': 'БАС', 'Б4С': 'БАС', 'БА0': 'БАС'
        }
        
        text_upper = original_text
        for wrong, correct in bas_corrections.items():
            if wrong in text_upper:
                text_upper = text_upper.replace(wrong, correct)
                corrections_made = True
        
        match = re.search(r'(\d{5})[\-–—]БАС', text_upper, re.UNICODE)
        if match:
            result = f"{match.group(1)}-БАС"
            return result, corrections_made
        
        digits = re.findall(r'\d+', text)
        if digits:
            result = f"{digits[0][:5].zfill(5)}-БАС"
            return result, True
        
        return "00000-БАС", True
    
    @staticmethod
    def parse_reg_number_certificate(text: str) -> Tuple[str, bool]:
        """Парсинг регистрационного номера удостоверения в формате 'ПАД-243'"""
        match = re.search(r'([А-ЯЁA-Z]{2,3})[\-–—]?(\d{3})', text.upper(), re.IGNORECASE)
        if match:
            letters = match.group(1)
            corrections_made = False
            
            letter_corrections = {'PAD': 'ПАД', 'ПAД': 'ПАД', 'П4Д': 'ПАД'}
            if letters in letter_corrections:
                letters = letter_corrections[letters]
                corrections_made = True
            
            return f"{letters}-{match.group(2)}", corrections_made
        
        return "ПАД-000", True
    
    @staticmethod
    def parse_full_name_diploma(text: str) -> Tuple[str, bool]:
        """Парсинг ФИО на двух строках для диплома"""
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
    def parse_full_name_certificate(text: str) -> Tuple[str, bool]:
        """Парсинг ФИО в одну строку для удостоверения"""
        result = text.strip()
        return result, len(result) < 8


class FinUnivParsers:
    """Паттерны парсинга для документов Финансового университета"""
    
    @staticmethod
    def parse_series_number_v1(text: str) -> Tuple[str, str, bool]:
        """Парсинг серии и номера для варианта 1 (ПК 773301156696)"""
        match = re.search(r'([А-ЯЁ]{2})\s+(\d+)', text.upper())
        if match:
            series = match.group(1)
            number = match.group(2)
            uncertain = len(number) < 8
            return series, number, uncertain
        
        match = re.search(r'([А-ЯЁ]{2})(\d+)', text.upper())
        if match:
            series = match.group(1)
            number = match.group(2)
            uncertain = len(number) < 8
            return series, number, uncertain
        
        return "ПК", "", True
    
    @staticmethod
    def parse_series_number_v2(text: str) -> Tuple[str, str, bool]:
        """Парсинг серии и номера для варианта 2"""
        return FinUnivParsers.parse_series_number_v1(text)
    
    @staticmethod
    def parse_reg_number_v1(text: str) -> Tuple[str, bool]:
        """Парсинг регистрационного номера (06.11д3/73)"""
        match = re.search(r'(\d+\.\d+[а-яё]*\d*/\d+)', text, re.IGNORECASE)
        if match:
            result = match.group(1)
            return result, len(result) < 5
        return text.strip(), True
    
    @staticmethod
    def parse_reg_number_v2(text: str) -> Tuple[str, bool]:
        """Парсинг регистрационного номера для варианта 2"""
        return FinUnivParsers.parse_reg_number_v1(text)
    
    @staticmethod
    def parse_full_name_simple(text: str) -> Tuple[str, bool]:
        """Простой парсинг ФИО в одну строку (вариант 1)"""
        result = text.strip()
        return result, len(result) < 8
    
    @staticmethod
    def parse_full_name_complex(text: str) -> Tuple[str, bool]:
        """
        Сложный парсинг ФИО из дательного падежа (вариант 2)
        Обработка текста на подчеркиваниях
        """
        cleaned_text = re.sub(r'[_\-=~—–]{2,}', ' ', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        patterns = [
            r'выдано?\s+([А-ЯЁ][а-яё]+у)\s+([А-ЯЁ][а-яё]+у)\s+([А-ЯЁ][а-яё]+у)',
            r'([А-ЯЁ][а-яё]+у)\s+([А-ЯЁ][а-яё]+у)\s+([А-ЯЁ][а-яё]+у)',
            r'([А-ЯЁ]\w+)\s+([А-ЯЁ]\w+)\s+([А-ЯЁ]\w+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                surname, name, patronymic = match.groups()
                
                if surname.endswith('у'):
                    surname = surname[:-1]
                if name.endswith('у'):
                    name = name[:-1]
                if patronymic.endswith('у'):
                    patronymic = patronymic + 'ич'
                
                result = f"{surname} {name} {patronymic}"
                return result, True
        
        result = cleaned_text.strip()
        return result, True
    
    @staticmethod
    def parse_date_from_text(text: str) -> Tuple[str, bool]:
        """
        Улучшенное извлечение даты с обработкой OCR-артефактов
        Примеры: '›« 30» ноября 2024 г.', 'о« 30» ноября 2024 г'
        """
        date_patterns = [
            r'"(\d{1,2})"\s+([а-яё]+)\s+(\d{4})',
            r'[›о«]*\s*«?\s*(\d{1,2})\s*[»"]*\s+([а-яё]+)\s+(\d{4})',
            r'[^\d]*(\d{1,2})[^\w]*\s*([а-яё]+)\s+(\d{4})',
            r'(\d{1,2})\s+([а-яё]+)\s+(\d{4})'
        ]
        
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
            'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                day, month_str, year = match.groups()
                month = months.get(month_str.lower())
                if month:
                    try:
                        result = datetime(int(year), month, int(day)).date().isoformat()
                        return result, False
                    except ValueError:
                        continue
        
        return text.strip(), True
