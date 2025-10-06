// Дополнительная интерактивность для OCR платформы

document.addEventListener('DOMContentLoaded', function() {
    
    // Улучшение drag-and-drop области
    const uploadAreas = document.querySelectorAll('[id*="upload"]');
    
    uploadAreas.forEach(area => {
        area.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.style.background = 'linear-gradient(145deg, #e3f2fd, #bbdefb)';
            this.style.borderColor = '#2196f3';
        });
        
        area.addEventListener('dragleave', function(e) {
            e.preventDefault();
            this.style.background = '';
            this.style.borderColor = '';
        });
        
        area.addEventListener('drop', function(e) {
            this.style.background = '';
            this.style.borderColor = '';
        });
    });
    
    // Анимация появления результатов
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1 && node.classList) {
                    if (node.classList.contains('result-card') || 
                        node.querySelector && node.querySelector('.result-card')) {
                        node.style.opacity = '0';
                        node.style.transform = 'translateY(20px)';
                        
                        setTimeout(() => {
                            node.style.transition = 'all 0.6s ease';
                            node.style.opacity = '1';
                            node.style.transform = 'translateY(0)';
                        }, 100);
                    }
                }
            });
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Копирование результатов в буфер обмена
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(function() {
            // Показываем уведомление
            showNotification('Скопировано в буфер обмена!', 'success');
        });
    }
    
    // Уведомления
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} notification-toast`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            animation: slideInRight 0.3s ease;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl+Enter - запуск OCR
        if (e.ctrlKey && e.key === 'Enter') {
            const ocrButton = document.querySelector('[id*="run-ocr"]');
            if (ocrButton && !ocrButton.disabled) {
                ocrButton.click();
            }
        }
        
        // Escape - закрытие модальных окон
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('.modal.show');
            modals.forEach(modal => {
                const closeBtn = modal.querySelector('.btn-close, [data-bs-dismiss="modal"]');
                if (closeBtn) closeBtn.click();
            });
        }
    });
    
    // Сохранение состояния формы в localStorage
    const inputs = document.querySelectorAll('select, input[type="text"], input[type="number"]');
    inputs.forEach(input => {
        // Загружаем сохраненное значение
        const savedValue = localStorage.getItem(`ocr_${input.id}`);
        if (savedValue && input.value === '') {
            input.value = savedValue;
        }
        
        // Сохраняем при изменении
        input.addEventListener('change', function() {
            localStorage.setItem(`ocr_${this.id}`, this.value);
        });
    });
    
    // Добавляем стили для анимаций
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(300px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(300px); opacity: 0; }
        }
        
        .notification-toast {
            max-width: 300px;
            word-wrap: break-word;
        }
    `;
    document.head.appendChild(style);
});
