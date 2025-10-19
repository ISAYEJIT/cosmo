// Table sorting functionality for NOAA alerts

// Функция для сортировки таблицы
function sortTable(columnIndex) {
    const table = document.getElementById("alertsTable");
    if (!table) return;
    
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.rows);
    
    // Определяем направление сортировки
    const currentSort = table.getAttribute('data-sort-column');
    const currentDirection = table.getAttribute('data-sort-direction') || 'asc';
    const newDirection = (currentSort == columnIndex && currentDirection === 'asc') ? 'desc' : 'asc';
    
    // Сортируем строки
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        
        // Специальная обработка для дат (колонка 2 - время выпуска)
        if (columnIndex === 2) {
            const aDate = new Date(aText.replace(' UTC', ''));
            const bDate = new Date(bText.replace(' UTC', ''));
            return newDirection === 'asc' ? aDate - bDate : bDate - aDate;
        }
        
        // Обычная сортировка по тексту
        if (newDirection === 'asc') {
            return aText.localeCompare(bText);
        } else {
            return bText.localeCompare(aText);
        }
    });
    
    // Очищаем tbody и добавляем отсортированные строки
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
    
    // Сохраняем состояние сортировки
    table.setAttribute('data-sort-column', columnIndex);
    table.setAttribute('data-sort-direction', newDirection);
    
    // Обновляем иконки сортировки
    updateSortIcons(columnIndex, newDirection);
}

// Функция для обновления иконок сортировки
function updateSortIcons(sortedColumn, direction) {
    const headers = document.querySelectorAll('#alertsTable th');
    headers.forEach((header, index) => {
        const sortIcon = header.querySelector('.fa-sort, .fa-sort-up, .fa-sort-down');
        if (sortIcon) {
            if (index === sortedColumn) {
                sortIcon.className = direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
            } else {
                sortIcon.className = 'fas fa-sort';
            }
        }
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Сортируем по времени выпуска по умолчанию (новые сверху) - колонка 2
    if (document.getElementById("alertsTable")) {
        sortTable(2);
        sortTable(2); // Два раза для сортировки по убыванию
    }
});

