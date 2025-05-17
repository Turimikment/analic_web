 document.addEventListener('DOMContentLoaded', function() {
    const link = document.createElement('a');
    link.href = '/';
    link.innerHTML = '🏠 Вернуться в норку';
    link.style.position = 'fixed';
    link.style.bottom = '20px';
    link.style.right = '20px';
    link.style.padding = '12px 24px';
    link.style.backgroundColor = '#FF9800';
    link.style.color = 'white';
    link.style.borderRadius = '25px';
    link.style.textDecoration = 'none';
    link.style.zIndex = '9999';
    link.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
    link.style.transition = 'transform 0.3s';
    
    link.addEventListener('mouseover', () => {
        link.style.transform = 'rotate(-2deg) scale(1.05)';
    });
    
    link.addEventListener('mouseout', () => {
        link.style.transform = 'none';
    });

    document.body.appendChild(link);
});