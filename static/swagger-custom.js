function addBackButton() {
    const backButton = document.createElement('a');
    backButton.href = '/';
    backButton.innerHTML = '🏠 Вернуться на главную';
    backButton.id = 'custom-back-button';
    
    // Стилизация
    Object.assign(backButton.style, {
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        padding: '10px 20px',
        backgroundColor: '#FF9800',
        color: 'white',
        borderRadius: '25px',
        textDecoration: 'none',
        zIndex: '99999',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
        transition: 'transform 0.3s'
    });

    backButton.addEventListener('mouseenter', () => {
        backButton.style.transform = 'rotate(-3deg) scale(1.05)';
    });
    
    backButton.addEventListener('mouseleave', () => {
        backButton.style.transform = 'none';
    });

    document.body.appendChild(backButton);
}

// Отслеживаем появление Swagger UI
const observer = new MutationObserver((mutations) => {
    if (document.querySelector('.swagger-ui')) {
        addBackButton();
        observer.disconnect();
    }
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});