"""
OCR Платформа для документов
Главная точка входа в приложение
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional
import platform

PROJECT_ROOT = Path(__file__).parent.absolute()
CORE_PATH = PROJECT_ROOT / 'core'
WEB_PATH = PROJECT_ROOT / 'web'

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CORE_PATH))
sys.path.insert(0, str(WEB_PATH))

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
    """Валидатор системных требований и зависимостей"""
    
    @staticmethod
    def check_python_version() -> bool:
        """Проверка версии Python"""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            logger.error(f"Требуется Python 3.8+, текущая версия: {version.major}.{version.minor}")
            return False
        logger.info(f"Python {version.major}.{version.minor}.{version.micro}")
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
                elif import_name == 'cv2':
                    import cv2
                elif import_name == 'fitz':
                    import fitz
                else:
                    __import__(import_name)
            except ImportError:
                missing_packages.append(package_name)
        
        if missing_packages:
            logger.error(f"Отсутствуют пакеты: {', '.join(missing_packages)}")
            logger.error(f"Установите: pip install {' '.join(missing_packages)}")
            return False
        
        logger.info("Все зависимости установлены")
        return True
    
    @staticmethod
    def check_tesseract() -> Optional[str]:
        """Поиск и проверка Tesseract OCR"""
        possible_paths = []
        
        if platform.system() == 'Windows':
            possible_paths.extend([
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe")
            ])
        else:
            possible_paths.extend([
                "/usr/bin/tesseract",
                "/usr/local/bin/tesseract",
                "/opt/homebrew/bin/tesseract"
            ])
        
        env_path = os.environ.get('TESSERACT_PATH')
        if env_path:
            possible_paths.insert(0, env_path)
        
        for path in possible_paths:
            if path and os.path.isfile(path):
                logger.info(f"Tesseract найден: {path}")
                return path
        
        import shutil
        tesseract_path = shutil.which('tesseract')
        if tesseract_path:
            logger.info(f"Tesseract найден через PATH: {tesseract_path}")
            return tesseract_path
        
        logger.warning("Tesseract не найден автоматически")
        return None
    
    @staticmethod
    def validate_project_structure() -> bool:
        """Проверка структуры проекта"""
        required_files = {
            'core/ocr_engine.py': 'OCR движок',
            'core/config.py': 'Конфигурации документов',
            'core/parsers.py': 'Парсеры полей',
            'core/image_processor.py': 'Процессор изображений',
            'web/dashboard.py': 'Dash интерфейс'
        }
        
        missing_files = []
        
        for file_path, description in required_files.items():
            full_path = PROJECT_ROOT / file_path
            if not full_path.exists():
                missing_files.append(f"{file_path} ({description})")
                logger.error(f"Отсутствует: {file_path}")
        
        if missing_files:
            logger.error("Отсутствуют файлы:")
            for file in missing_files:
                logger.error(f"   - {file}")
            return False
        
        logger.info("Структура проекта корректна")
        return True


class ConfigurationManager:
    """Менеджер конфигураций приложения"""
    
    @staticmethod
    def load_core_modules() -> bool:
        """Загрузка и проверка core модулей"""
        try:
            logger.info("Загрузка core модулей...")
            
            from core.config import get_config, DOCUMENT_CONFIGS
            from core.parsers import (
                OneTParsers, RosNouParsers, FinUnivParsers, CommonParsers
            )
            from core.ocr_engine import DocumentProcessor, OCREngine
            from core.image_processor import AdvancedImageProcessor
            
            logger.info("Все core модули загружены")
            logger.info(f"Доступно конфигураций: {len(DOCUMENT_CONFIGS)}")
            
            return True
            
        except ImportError as e:
            logger.error(f"Ошибка импорта core модулей: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки модулей: {e}")
            return False
    
    @staticmethod
    def validate_configurations() -> bool:
        """Валидация всех конфигураций документов"""
        try:
            from core.config import DOCUMENT_CONFIGS
            
            logger.info("Валидация конфигураций документов...")
            
            valid_count = 0
            
            for config_id, config in DOCUMENT_CONFIGS.items():
                try:
                    if not config.fields or not config.patterns:
                        logger.warning(f"{config_id}: нет полей или парсеров")
                        continue
                    
                    valid_count += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка валидации {config_id}: {e}")
            
            logger.info(f"Валидные конфигурации: {valid_count}/{len(DOCUMENT_CONFIGS)}")
            return valid_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка валидации конфигураций: {e}")
            return False


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='OCR Платформа для документов',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--host', default='127.0.0.1', help='IP адрес (по умолчанию: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8050, help='Порт (по умолчанию: 8050)')
    # ИСПРАВЛЕНО: debug по умолчанию False для production
    parser.add_argument('--debug', action='store_true', default=False, help='Включить режим отладки')
    parser.add_argument('--tesseract-path', help='Путь к Tesseract')
    parser.add_argument('--validate-only', action='store_true', help='Только проверка без запуска')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Уровень логирования')
    
    return parser.parse_args()


def main():
    """Главная функция запуска приложения"""
    args = parse_arguments()
    
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("Инициализация OCR платформы")
    
    if not SystemValidator.check_python_version():
        sys.exit(1)
    
    if not SystemValidator.validate_project_structure():
        sys.exit(1)
    
    if not SystemValidator.check_dependencies():
        sys.exit(1)
    
    tesseract_path = args.tesseract_path or SystemValidator.check_tesseract()
    
    if not tesseract_path:
        logger.error("Tesseract не найден!")
        logger.error("Установите Tesseract OCR:")
        logger.error("   Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        logger.error("   Linux: sudo apt install tesseract-ocr tesseract-ocr-rus")
        logger.error("   Mac: brew install tesseract tesseract-lang")
        sys.exit(1)
    
    if not ConfigurationManager.load_core_modules():
        sys.exit(1)
    
    if not ConfigurationManager.validate_configurations():
        sys.exit(1)
    
    if args.validate_only:
        logger.info("Валидация успешно завершена")
        return
    
    try:
        from web.dashboard import create_dash_app
        
        app = create_dash_app(tesseract_cmd=tesseract_path)
        
        logger.info(f"OCR Платформа запущена: http://{args.host}:{args.port}")
        logger.info(f"Режим отладки: {'включен' if args.debug else 'выключен'}")
        logger.info(f"Логи: {LOG_FILE}")
        
        app.run_server(debug=args.debug, host=args.host, port=args.port)
        
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
    except ImportError as e:
        logger.error(f"Ошибка импорта Dashboard: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
