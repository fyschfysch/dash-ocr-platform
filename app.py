"""
🔍 OCR Платформа для документов
Главная точка входа в приложение

Система распознавания документов о переподготовке и повышении квалификации
с интерактивной разметкой полей для новых типов документов.

Поддерживаемые организации:
- 1Т (удостоверения и дипломы)
- РОСНОУ (удостоверения и дипломы) 
- Финансовый университет (удостоверения 2 варианта)
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

# Добавляем пути к модулям
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
    """
    Проверка наличия всех необходимых зависимостей
    """
    required_packages = [
        'dash', 'dash_bootstrap_components', 'plotly',
        'PIL', 'cv2', 'numpy', 'pandas',
        'pytesseract', 'fitz', 're', 'json'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'PIL':
                from PIL import Image
            elif package == 'cv2':
                import cv2
            elif package == 'fitz':
                import fitz
            else:
                __import__(package)
            
            logger.debug(f"✅ {package} - OK")
            
        except ImportError as e:
            missing_packages.append(package)
            logger.error(f"❌ {package} - НЕ НАЙДЕН: {e}")
    
    if missing_packages:
        logger.error(f"Отсутствуют пакеты: {missing_packages}")
        logger.error("Установите их командой: pip install -r requirements.txt")
        return False
    
    logger.info("✅ Все зависимости установлены")
    return True


def find_tesseract():
    """
    Автоматический поиск Tesseract в системе
    """
    possible_paths = [
        # Windows
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(
            os.environ.get('USERNAME', '')
        ),
        
        # Linux/Mac
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
        
        # Путь из переменной окружения
        os.environ.get('TESSERACT_PATH', '')
    ]
    
    for path in possible_paths:
        if path and os.path.isfile(path):
            logger.info(f"✅ Tesseract найден: {path}")
            return path
    
    # Попробуем найти через which/where
    import shutil
    tesseract_path = shutil.which('tesseract')
    if tesseract_path:
        logger.info(f"✅ Tesseract найден через PATH: {tesseract_path}")
        return tesseract_path
    
    logger.warning("⚠️ Tesseract не найден автоматически")
    logger.warning("Укажите путь через переменную TESSERACT_PATH или параметр --tesseract-path")
    return None


def validate_project_structure():
    """
    Проверка структуры проекта
    """
    required_files = [
        'core/ocr_engine.py',
        'core/config.py', 
        'web/dashboard.py',
        'web/markup_tool.py'
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


def create_requirements_file():
    """
    Создание файла requirements.txt
    """
    requirements = """# OCR Platform Dependencies
dash>=2.14.0
dash-bootstrap-components>=1.5.0
plotly>=5.17.0
Pillow>=10.0.0
opencv-python>=4.8.0
numpy>=1.24.0
pandas>=2.1.0
pytesseract>=0.3.10
PyMuPDF>=1.23.0
python-dateutil>=2.8.2

# Optional: для работы с морфологией (будущие возможности)
# pymorphy2>=0.9.1
"""
    
    req_file = PROJECT_ROOT / 'requirements.txt'
    if not req_file.exists():
        with open(req_file, 'w', encoding='utf-8') as f:
            f.write(requirements)
        logger.info(f"✅ Создан файл {req_file}")
    
    return req_file


def print_startup_info():
    """
    Вывод информации о запуске
    """
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
    """
    Главная функция приложения
    """
    parser = argparse.ArgumentParser(
        description='🔍 OCR Платформа для документов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python app.py                                    # Запуск с автопоиском Tesseract
  python app.py --port 8080                       # Запуск на порту 8080
  python app.py --tesseract-path /path/to/tesseract # Указание пути к Tesseract
  python app.py --host 0.0.0.0 --port 80         # Запуск для внешнего доступа
        """
    )
    
    parser.add_argument(
        '--host', 
        default='127.0.0.1',
        help='IP адрес для запуска сервера (по умолчанию: 127.0.0.1)'
    )
    
    parser.add_argument(
        '--port', 
        type=int, 
        default=8050,
        help='Порт для запуска сервера (по умолчанию: 8050)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Запуск в режиме отладки'
    )
    
    parser.add_argument(
        '--tesseract-path',
        help='Путь к исполняемому файлу Tesseract'
    )
    
    parser.add_argument(
        '--create-requirements',
        action='store_true',
        help='Создать файл requirements.txt и выйти'
    )
    
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Только проверить зависимости и выйти'
    )
    
    args = parser.parse_args()
    
    # Создание requirements.txt
    if args.create_requirements:
        req_file = create_requirements_file()
        print(f"✅ Создан файл: {req_file}")
        print("📦 Установите зависимости командой: pip install -r requirements.txt")
        return
    
    # Проверка структуры проекта
    if not validate_project_structure():
        logger.error("❌ Проблемы со структурой проекта. Проверьте наличие всех файлов.")
        sys.exit(1)
    
    # Проверка зависимостей
    if not check_dependencies():
        logger.error("❌ Отсутствуют необходимые пакеты")
        req_file = create_requirements_file()
        print(f"📦 Установите зависимости: pip install -r {req_file}")
        sys.exit(1)
    
    # Только проверка
    if args.check_only:
        logger.info("✅ Все проверки пройдены успешно")
        return
    
    # Поиск Tesseract
    tesseract_path = args.tesseract_path or find_tesseract()
    if not tesseract_path:
        logger.error("❌ Tesseract не найден!")
        logger.error("Установите Tesseract OCR:")
        logger.error("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        logger.error("  Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-rus")
        logger.error("  MacOS: brew install tesseract tesseract-lang")
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
        logger.error("Проверьте структуру проекта и установку зависимостей")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        sys.exit(1)


if __name__ == '__main__':
    main()
