document.addEventListener('DOMContentLoaded', function() {
    // Создаем кнопку
    const backButton = document.createElement('a');
    backButton.href = '/';
    backButton.innerHTML = '🏠 Вернуться на главную';
    backButton.style.position = 'fixed';
    backButton.style.bottom = '20px';
    backButton.style.right = '20px';
    backButton.style.padding = '10px 20px';
    backButton.style.backgroundColor = '#FF9800';
    backButton.style.color = 'white';
    backButton.style.borderRadius = '25px';
    backButton.style.textDecoration = 'none';
    backButton.style.zIndex = '9999';
    backButton.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
    backButton.style.transition = 'transform 0.3s';

    // Анимация при наведении
    backButton.addEventListener('mouseenter', () => {
        backButton.style.transform = 'rotate(-3deg) scale(1.05)';
    });
    
    backButton.addEventListener('mouseleave', () => {
        backButton.style.transform = 'none';
    });

    // Добавляем кнопку в DOM
    document.body.appendChild(backButton);

    console.log('Custom Swagger button initialized!');  // Для отладки
});