#!/usr/bin/env python3
"""
🔍 OCR Платформа для документов
Главная точка входа в приложение

Полнофункциональная система распознавания документов о переподготовке 
и повышении квалификации с интерактивным редактированием полей.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional
import platform

# Настройка путей
PROJECT_ROOT = Path(__file__).parent.absolute()
CORE_PATH = PROJECT_ROOT / 'core'
WEB_PATH = PROJECT_ROOT / 'web'

# Добавляем пути в sys.path
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CORE_PATH))
sys.path.insert(0, str(WEB_PATH))

# Настройка логирования
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = PROJECT_ROOT / 'ocr_platform.log'

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a')
    ]
)

logger = logging.getLogger(__name__)


class SystemValidator:
    """
    Валидатор системных требований и зависимостей
    """
    
    @staticmethod
    def check_python_version() -> bool:
        """Проверка версии Python"""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            logger.error(f"❌ Требуется Python 3.8+, текущая версия: {version.major}.{version.minor}")
            return False
        
        logger.info(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    
    @staticmethod
    def check_dependencies() -> bool:
        """Проверка наличия всех необходимых зависимостей"""
        required_packages = {
            'dash': 'dash',
            'dash_bootstrap_components': 'dash-bootstrap-components',
            'plotly': 'plotly',
            'PIL': 'Pillow',
            'cv2': 'opencv-python',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'pytesseract': 'pytesseract',
            'fitz': 'PyMuPDF'
        }
        
        missing_packages = []
        
        for import_name, package_name in required_packages.items():
            try:
                if import_name == 'PIL':
                    from PIL import Image
                    logger.debug(f"✅ {package_name} - OK")
                elif import_name == 'cv2':
                    import cv2
                    logger.debug(f"✅ {package_name} - OK")
                elif import_name == 'fitz':
                    import fitz
                    logger.debug(f"✅ {package_name} - OK")
                else:
                    __import__(import_name)
                    logger.debug(f"✅ {package_name} - OK")
                    
            except ImportError as e:
                missing_packages.append(package_name)
                logger.error(f"❌ {package_name} - НЕ НАЙДЕН: {e}")
        
        if missing_packages:
            logger.error(f"\n❌ Отсутствуют пакеты: {', '.join(missing_packages)}")
            logger.error("Установите их командой:")
            logger.error(f"pip install {' '.join(missing_packages)}")
            return False
        
        logger.info("✅ Все зависимости установлены")
        return True
    
    @staticmethod
    def check_tesseract() -> Optional[str]:
        """Поиск и проверка Tesseract OCR"""
        possible_paths = []
        
        # Windows пути
        if platform.system() == 'Windows':
            possible_paths.extend([
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe")
            ])
        
        # Linux/Mac пути
        else:
            possible_paths.extend([
                "/usr/bin/tesseract",
                "/usr/local/bin/tesseract",
                "/opt/homebrew/bin/tesseract"
            ])
        
        # Проверяем переменную окружения
        env_path = os.environ.get('TESSERACT_PATH')
        if env_path:
            possible_paths.insert(0, env_path)
        
        # Ищем в известных путях
        for path in possible_paths:
            if path and os.path.isfile(path):
                logger.info(f"✅ Tesseract найден: {path}")
                return path
        
        # Пробуем найти через which/where
        import shutil
        tesseract_path = shutil.which('tesseract')
        if tesseract_path:
            logger.info(f"✅ Tesseract найден через PATH: {tesseract_path}")
            return tesseract_path
        
        logger.warning("⚠️ Tesseract не найден автоматически")
        logger.warning("Укажите путь через --tesseract-path или установите переменную TESSERACT_PATH")
        return None
    
    @staticmethod
    def validate_project_structure() -> bool:
        """Проверка структуры проекта"""
        required_files = {
            'core/ocr_engine.py': 'OCR движок',
            'core/config.py': 'Конфигурации документов',
            'core/parsers.py': 'Парсеры полей',
            'core/image_processor.py': 'Процессор изображений',
            'web/dashboard.py': 'Dash интерфейс',
            'requirements.txt': 'Зависимости'
        }
        
        missing_files = []
        
        for file_path, description in required_files.items():
            full_path = PROJECT_ROOT / file_path
            if not full_path.exists():
                missing_files.append(f"{file_path} ({description})")
                logger.error(f"❌ Отсутствует: {file_path}")
            else:
                logger.debug(f"✅ {file_path}")
        
        if missing_files:
            logger.error(f"\n❌ Отсутствуют файлы:")
            for file in missing_files:
                logger.error(f"   - {file}")
            return False
        
        logger.info("✅ Структура проекта корректна")
        return True


class ConfigurationManager:
    """
    Менеджер конфигураций приложения
    """
    
    @staticmethod
    def load_core_modules() -> bool:
        """Загрузка и проверка core модулей"""
        try:
            logger.info("Загрузка core модулей...")
            
            # Импортируем все модули
            from core.config import get_available_configs, get_config
            from core.parsers import ParserRegistry
            from core.ocr_engine import DocumentProcessor
            from core.image_processor import AdvancedImageProcessor
            
            logger.info("✅ Все core модули загружены")
            
            # Проверяем доступные конфигурации
            configs = get_available_configs()
            logger.info(f"✅ Доступно конфигураций: {len(configs)}")
            
            for conf in configs:
                logger.debug(f"   - {conf['organization']}: {conf['name']}")
            
            # Проверяем парсеры
            parsers = ParserRegistry.list_parsers()
            logger.info(f"✅ Доступно парсеров: {len(parsers)}")
            for parser in parsers:
                logger.debug(f"   - {parser}")
            
            return True
            
        except ImportError as e:
            logger.error(f"❌ Ошибка импорта core модулей: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модулей: {e}")
            return False
    
    @staticmethod
    def validate_configurations() -> bool:
        """Валидация всех конфигураций документов"""
        try:
            from core.config import DOCUMENT_CONFIGS, validate_config
            
            logger.info("Валидация конфигураций документов...")
            
            valid_count = 0
            invalid_count = 0
            
            for config_id, config_func in DOCUMENT_CONFIGS.items():
                try:
                    config = config_func()
                    errors = validate_config(config)
                    
                    if errors:
                        logger.warning(f"⚠️ {config_id}: {len(errors)} предупреждений")
                        for error in errors:
                            logger.debug(f"      - {error}")
                        invalid_count += 1
                    else:
                        valid_count += 1
                        logger.debug(f"✅ {config_id}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка валидации {config_id}: {e}")
                    invalid_count += 1
            
            logger.info(f"✅ Валидные конфигурации: {valid_count}/{len(DOCUMENT_CONFIGS)}")
            
            if invalid_count > 0:
                logger.warning(f"⚠️ Конфигурации с предупреждениями: {invalid_count}")
            
            return valid_count > 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации конфигураций: {e}")
            return False


def print_startup_banner():
    """Вывод приветственного баннера"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║         🔍 OCR ПЛАТФОРМА ДЛЯ ДОКУМЕНТОВ                                 ║
║         Система распознавания с интерактивным редактированием            ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

📋 ПОДДЕРЖИВАЕМЫЕ ОРГАНИЗАЦИИ:
   🏢 1Т
      ✓ Удостоверения о повышении квалификации
      ✓ Дипломы о профессиональной переподготовке

   🏛️ РОСНОУ (Российский новый университет)
      ✓ Удостоверения о повышении квалификации
      ✓ Дипломы о профессиональной переподготовке

   🏦 Финансовый университет
      ✓ Удостоверения (вариант 1) - ФИО в одну строку
      ✓ Удостоверения (вариант 2) - ФИО на трёх строках ⚠️

🔧 ИЗВЛЕКАЕМЫЕ ПОЛЯ:
   • ФИО (в именительном падеже)
   • Серия и номер документа
   • Регистрационный номер
   • Дата выдачи (в ISO формате)

✨ ВОЗМОЖНОСТИ:
   • Превью первой страницы PDF на всю ширину экрана
   • Таблица с миниатюрами вырезанных полей
   • Интерактивное редактирование распознанных значений
   • Цветовая индикация полей, требующих проверки
   • Кнопки принятия исправлений для каждого поля
   • Экспорт результатов в CSV/JSON

════════════════════════════════════════════════════════════════════════════
"""
    print(banner)


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='🔍 OCR Платформа для документов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python app.py
  python app.py --port 8080
  python app.py --tesseract-path "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
  python app.py --host 0.0.0.0 --port 80 --no-debug
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
        default=True,
        help='Запуск в режиме отладки (по умолчанию: включен)'
    )
    
    parser.add_argument(
        '--no-debug',
        action='store_false',
        dest='debug',
        help='Отключить режим отладки'
    )
    
    parser.add_argument(
        '--tesseract-path',
        help='Путь к исполняемому файлу Tesseract'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Только проверить систему без запуска'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Уровень логирования'
    )
    
    return parser.parse_args()


def main():
    """
    Главная функция запуска приложения
    """
    # Парсинг аргументов
    args = parse_arguments()
    
    # Установка уровня логирования
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Вывод баннера
    print_startup_banner()
    
    logger.info("=" * 80)
    logger.info("Начало инициализации OCR платформы")
    logger.info("=" * 80)
    
    # Шаг 1: Проверка Python версии
    logger.info("\n[1/7] Проверка версии Python...")
    if not SystemValidator.check_python_version():
        sys.exit(1)
    
    # Шаг 2: Проверка структуры проекта
    logger.info("\n[2/7] Проверка структуры проекта...")
    if not SystemValidator.validate_project_structure():
        logger.error("❌ Структура проекта некорректна")
        sys.exit(1)
    
    # Шаг 3: Проверка зависимостей
    logger.info("\n[3/7] Проверка зависимостей...")
    if not SystemValidator.check_dependencies():
        logger.error("❌ Не все зависимости установлены")
        sys.exit(1)
    
    # Шаг 4: Поиск Tesseract
    logger.info("\n[4/7] Поиск Tesseract OCR...")
    tesseract_path = args.tesseract_path or SystemValidator.check_tesseract()
    
    if not tesseract_path:
        logger.error("❌ Tesseract не найден!")
        logger.error("Скачайте и установите Tesseract OCR:")
        logger.error("   Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        logger.error("   Linux: sudo apt install tesseract-ocr tesseract-ocr-rus")
        logger.error("   Mac: brew install tesseract tesseract-lang")
        sys.exit(1)
    
    # Шаг 5: Загрузка модулей
    logger.info("\n[5/7] Загрузка core модулей...")
    if not ConfigurationManager.load_core_modules():
        logger.error("❌ Ошибка загрузки модулей")
        sys.exit(1)
    
    # Шаг 6: Валидация конфигураций
    logger.info("\n[6/7] Валидация конфигураций документов...")
    if not ConfigurationManager.validate_configurations():
        logger.error("❌ Ошибка валидации конфигураций")
        sys.exit(1)
    
    # Если только валидация
    if args.validate_only:
        logger.info("\n" + "=" * 80)
        logger.info("✅ Валидация успешно завершена!")
        logger.info("=" * 80)
        return
    
    # Шаг 7: Запуск Dashboard
    logger.info("\n[7/7] Запуск OCR Dashboard...")
    
    try:
        from web.dashboard import OCRDashboard
        
        # Создание и запуск Dashboard
        dashboard = OCRDashboard(tesseract_cmd=tesseract_path)
        
        logger.info("\n" + "=" * 80)
        logger.info(f"🌐 OCR Платформа запущена!")
        logger.info(f"📱 Откройте браузер: http://{args.host}:{args.port}")
        logger.info(f"🔧 Режим отладки: {'включен' if args.debug else 'выключен'}")
        logger.info(f"📁 Логи: {LOG_FILE}")
        logger.info("🛑 Для остановки нажмите Ctrl+C")
        logger.info("=" * 80 + "\n")
        
        # Запуск сервера
        dashboard.run_server(
            debug=args.debug,
            host=args.host,
            port=args.port
        )
        
    except KeyboardInterrupt:
        logger.info("\n\n👋 Приложение остановлено пользователем")
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта Dashboard: {e}")
        logger.error("Проверьте наличие файла web/dashboard.py")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        sys.exit(1)


if __name__ == '__main__':
    main()
