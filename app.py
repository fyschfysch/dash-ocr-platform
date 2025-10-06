"""
🔍 OCR Платформа для документов
Главная точка входа в приложение (Dash 3.0+ совместимый)

Система распознавания документов о переподготовке и повышении квалификации
с интерактивной разметкой полей для новых типов документов.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional

# Настройка путей
PROJECT_ROOT = Path(__file__).parent.absolute()
CORE_PATH = PROJECT_ROOT / 'core'
WEB_PATH = PROJECT_ROOT / 'web'

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CORE_PATH))
sys.path.insert(0, str(WEB_PATH))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / 'ocr_platform.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def check_dependencies():
    """Проверка наличия всех необходимых зависимостей"""
    required_packages = [
        ('dash', 'dash'), ('dash_bootstrap_components', 'dash_bootstrap_components'),
        ('plotly', 'plotly'), ('PIL', 'PIL'), ('cv2', 'cv2'), 
        ('numpy', 'numpy'), ('pandas', 'pandas'), ('pytesseract', 'pytesseract'), 
        ('fitz', 'fitz'), ('re', 're'), ('json', 'json')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            if import_name == 'PIL':
                from PIL import Image
            elif import_name == 'cv2':
                import cv2
            elif import_name == 'fitz':
                import fitz
            else:
                __import__(import_name)
            
            logger.debug(f"✅ {package_name} - OK")
            
        except ImportError as e:
            missing_packages.append(package_name)
            logger.error(f"❌ {package_name} - НЕ НАЙДЕН: {e}")
    
    if missing_packages:
        logger.error(f"Отсутствуют пакеты: {missing_packages}")
        logger.error("Установите их командой: pip install -r requirements.txt")
        return False
    
    logger.info("✅ Все зависимости установлены")
    return True


def find_tesseract():
    """Автоматический поиск Tesseract в системе"""
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
        os.environ.get('TESSERACT_PATH', '')
    ]
    
    for path in possible_paths:
        if path and os.path.isfile(path):
            logger.info(f"✅ Tesseract найден: {path}")
            return path
    
    import shutil
    tesseract_path = shutil.which('tesseract')
    if tesseract_path:
        logger.info(f"✅ Tesseract найден через PATH: {tesseract_path}")
        return tesseract_path
    
    logger.warning("⚠️ Tesseract не найден автоматически")
    return None


def validate_project_structure():
    """Проверка структуры проекта"""
    required_files = [
        'core/ocr_engine.py', 'core/config.py', 
        'web/dashboard.py', 'web/markup_tool.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"❌ Отсутствуют файлы: {missing_files}")
        return False
    
    logger.info("✅ Структура проекта корректна")
    return True


def print_startup_info():
    """Вывод информации о запуске"""
    print("=" * 80)
    print("🔍 OCR ПЛАТФОРМА ДЛЯ РАСПОЗНАВАНИЯ СТРУКТУРИРОВАННЫХ ПОЛЕЙ ДОКУМЕНТОВ")
    print("=" * 80)
    print()
    print("📋 ПОДДЕРЖИВАЕМЫЕ ОРГАНИЗАЦИИ:")
    print("   🏢 1Т")
    print("      ✓ Удостоверения о повышении квалификации")
    print("      ✓ Дипломы о профессиональной переподготовке")
    print()
    print("   🏛️ РОСНОУ (Российский новый университет)")
    print("      ✓ Удостоверения о повышении квалификации")
    print("      ✓ Дипломы о профессиональной переподготовке") 
    print()
    print("   🏦 Финансовый университет")
    print("      ✓ Удостоверения (вариант 1) - ФИО в одну строку")
    print("      ✓ Удостоверения (вариант 2) - ФИО на трёх строках ⚠️")
    print()
    print("🔧 ИЗВЛЕКАЕМЫЕ ПОЛЯ:")
    print("   • ФИО (в именительном падеже)")
    print("   • Серия и номер документа")
    print("   • Регистрационный номер")
    print("   • Дата выдачи (в ISO формате)")
    print()
    print("=" * 80)


def main():
    """Главная функция приложения"""
    parser = argparse.ArgumentParser(
        description='🔍 OCR Платформа для документов (Dash 3.0+)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--host', default='127.0.0.1',
                       help='IP адрес для запуска сервера')
    parser.add_argument('--port', type=int, default=8050,
                       help='Порт для запуска сервера')
    parser.add_argument('--debug', action='store_true',
                       help='Запуск в режиме отладки')
    parser.add_argument('--tesseract-path',
                       help='Путь к исполняемому файлу Tesseract')
    
    args = parser.parse_args()
    
    # Проверка структуры проекта
    if not validate_project_structure():
        logger.error("❌ Проблемы со структурой проекта")
        sys.exit(1)
    
    # Проверка зависимостей
    if not check_dependencies():
        logger.error("❌ Отсутствуют необходимые пакеты")
        sys.exit(1)
    
    # Поиск Tesseract
    tesseract_path = args.tesseract_path or find_tesseract()
    if not tesseract_path:
        logger.error("❌ Tesseract не найден!")
        logger.error("Установите Tesseract OCR и укажите путь через --tesseract-path")
        sys.exit(1)
    
    # Вывод информации о запуске
    print_startup_info()
    
    try:
        # Импорт основного модуля
        from web.dashboard import OCRDashboard
        
        # Создание и запуск приложения
        logger.info("🚀 Инициализация OCR Dashboard...")
        dashboard = OCRDashboard(tesseract_cmd=tesseract_path)
        
        logger.info(f"🌐 Запуск веб-сервера на http://{args.host}:{args.port}")
        logger.info("📱 Откройте браузер и перейдите по указанному адресу")
        logger.info("🛑 Для остановки нажмите Ctrl+C")
        
        dashboard.run_server(
            debug=args.debug,
            host=args.host,
            port=args.port
        )
        
    except KeyboardInterrupt:
        logger.info("\n👋 Приложение остановлено пользователем")
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта модулей: {e}")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        sys.exit(1)


if __name__ == '__main__':
    main()
