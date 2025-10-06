#!/usr/bin/env python3
"""
OCR Платформа - упрощенная версия для отладки
"""

import os
import sys
import logging
from pathlib import Path

# Настройка путей
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'web'))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Главная функция"""
    print("🔍 OCR Платформа - запуск упрощенной версии")
    
    try:
        # Импорт упрощенной версии
        from web.dashboard import OCRDashboard
        
        # Создание и запуск
        dashboard = OCRDashboard()
        dashboard.run_server(debug=True, port=8050)
        
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        print("Попробуйте переустановить зависимости:")
        print("pip install dash dash-bootstrap-components")
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")


if __name__ == '__main__':
    main()
