"""
Глобальные настройки приложения
"""

import os

# Настройки Dash
DASH_DEBUG = os.getenv('DASH_DEBUG', 'True').lower() == 'true'
DASH_HOST = os.getenv('DASH_HOST', '127.0.0.1')
DASH_PORT = int(os.getenv('DASH_PORT', 8050))

# Настройки OCR
MAX_IMAGE_DIMENSION = int(os.getenv('MAX_IMAGE_DIMENSION', 1200))
TESSERACT_CMD = os.getenv('TESSERACT_CMD', None)

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'ocr_platform.log')
