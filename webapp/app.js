// ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================

const tg = window.Telegram?.WebApp;
let userId = null;
let userData = null;
let currentWorkspaceId = null;
let currentTask = null;
let allTasks = [];
let selectedPriority = 'medium';
let currentDate = new Date();
let selectedDate = null;
let currentFilter = 'all';
let isEditing = false;

// ==================== ИНИЦИАЛИЗАЦИЯ ====================

document.addEventListener('DOMContentLoaded', () => {
    init();
});

async function init() {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.enableClosingConfirmation();
        userId = tg.initDataUnsafe?.user?.id;
        
        if (tg.colorScheme === 'light') {
            document.body.classList.add('light-theme');
            document.querySelector('.theme-toggle').textContent = '☀️';
        }
    }
    
    if (!userId) {
        userId = 123456789;
    }
    
    updateCurrentDate();
    await loadUserData();
    setupEventListeners();
    renderCalendar();
}

// ==================== ЗАГРУЗКА ДАННЫХ ====================

async function loadUserData() {
    try {
        showLoading(true);
        const response = await fetch(`/api/user/${userId}`);
        
        if (!response.ok) {
            console.error('User not found');
            return;
        }
        
        const data = await response.json();
        userData = data;
        
        const name = tg?.initDataUnsafe?.user?.first_name || data.user.full_name || 'Друг';
        document.getElementById('greeting').textContent = `👋 Привет, ${name}!`;
        
        document.getElementById('profile-name').textContent = data.user.full_name || 'Пользователь';
        document.getElementById('profile-username').textContent = data.user.username ? `@${data.user.username}` : '';
        
        updateStats(data.stats);
        
        document.getElementById('profile-total').textContent = data.stats.total;
        document.getElementById('profile-done').textContent = data.stats.done;
        
        const personal = data.workspaces.find(w => w.is_personal);
        if (personal) {
            currentWorkspaceId = personal.id;
            await loadWorkspace(personal.id);
        }
        
        renderWorkspaces(data.workspaces);
        updateAchievements(data.stats.done);
        
    } catch (error) {
        console.error('Error loading user:', error);
        showToast('❌ Ошибка загрузки', 'error');
    } finally {
        showLoading(false);
    }
}

async function loadWorkspace(workspaceId) {
    try {
        const response = await fetch(`/api/workspace/${workspaceId}`);
        if (!response.ok) return;
        
        const data = await response.json();
        allTasks = data.tasks || [];
        
        renderBoard(data.funnels);
        renderTaskList(allTasks);
        renderTodayTasks();
        renderUrgentTasks();
        renderCalendar();
        
    } catch (error) {
        console.error('Error loading workspace:', error);
    }
}

// ==================== ОБНОВЛЕНИЕ СТАТИСТИКИ ====================

function updateStats(stats) {
    const done = stats.done || 0;
    const total = stats.total || 0;
    const percent = total > 0 ? Math.round(done / total * 100) : 0;
    
    document.getElementById('stat-done').textContent = done;
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-percent').textContent = percent + '%';
    document.getElementById('progress-fill').style.width = percent + '%';
}

function updateCurrentDate() {
    const options = { day: 'numeric', month: 'long' };
    const dateStr = new Date().toLocaleDateString('ru-RU', options);
    document.getElementById('current-date').textContent = dateStr;
}

// ==================== РЕНДЕРИНГ ====================

function renderBoard(funnels) {
    const board = document.getElementById('board');
    board.innerHTML = '';
    
    if (!funnels || funnels.length === 0) {
        board.innerHTML = '<div class="empty-state"><span class="empty-icon">📊</span><span>Нет воронок</span></div>';
        return;
    }
    
    const funnel = funnels[0];
    
    funnel.stages.forEach(stage => {
        const column = document.createElement('div');
        column.className = 'column';
        column.innerHTML = `
            <div class="column-header">
                <span class="column-title">${stage.name}</span>
                <span class="column-count">${stage.tasks.length}</span>
            </div>
            <div class="column-tasks" data-stage-id="${stage.id}">
                ${stage.tasks.map(task => renderTaskCard(task)).join('')}
            </div>
        `;
        board.appendChild(column);
    });
}

function renderTaskCard(task) {
    const isDone = task.status === 'done';
    return `
        <div class="task-card ${isDone ? 'done' : ''} priority-${task.priority}" 
             data-task-id="${task.id}" onclick="showTask(${task.id})">
            <div class="task-card-title">${escapeHtml(task.title)}</div>
            <div class="task-card-footer">
                <span class="task-card-date">${formatDate(task.created_at)}</span>
                <div class="task-card-check" onclick="event.stopPropagation(); toggleTask(${task.id})"></div>
            </div>
        </div>
    `;
}

function renderTaskList(tasks) {
    const list = document.getElementById('task-list');
    
    let filteredTasks = tasks;
    if (currentFilter === 'todo') {
        filteredTasks = tasks.filter(t => t.status !== 'done');
    } else if (currentFilter === 'done') {
        filteredTasks = tasks.filter(t => t.status === 'done');
    }
    
    if (!filteredTasks || filteredTasks.length === 0) {
        list.innerHTML = '<div class="empty-state"><span class="empty-icon">✨</span><span>Нет задач</span></div>';
        return;
    }
    
    list.innerHTML = filteredTasks.map(task => renderTaskItem(task)).join('');
}

function renderTaskItem(task) {
    const isDone = task.status === 'done';
    return `
        <div class="task-item ${isDone ? 'done' : ''} priority-${task.priority}" 
             onclick="showTask(${task.id})">
            <div class="task-checkbox" onclick="event.stopPropagation(); toggleTask(${task.id})"></div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title)}</div>
                <div class="task-meta">
                    <span class="task-meta-item">📅 ${formatDate(task.created_at)}</span>
                </div>
            </div>
            <div class="task-actions-mini">
                <button class="mini-btn edit" onclick="event.stopPropagation(); editTask(${task.id})">✏️</button>
                <button class="mini-btn delete" onclick="event.stopPropagation(); confirmDeleteTask(${task.id})">🗑</button>
            </div>
        </div>
    `;
}

function renderTodayTasks() {
    const container = document.getElementById('today-tasks');
    const today = new Date().toDateString();
    
    const todayTasks = allTasks.filter(t => {
        const taskDate = new Date(t.created_at).toDateString();
        return taskDate === today && t.status !== 'done';
    });
    
    document.getElementById('today-count').textContent = todayTasks.length;
    
    if (todayTasks.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">🎉</span><span>На сегодня всё сделано!</span></div>';
        return;
    }
    
    container.innerHTML = todayTasks.slice(0, 5).map(task => renderTaskItem(task)).join('');
}

function renderUrgentTasks() {
    const container = document.getElementById('urgent-tasks');
    
    const urgentTasks = allTasks.filter(t => t.priority === 'high' && t.status !== 'done');
    
    document.getElementById('urgent-count').textContent = urgentTasks.length;
    
    if (urgentTasks.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">😌</span><span>Нет срочных задач</span></div>';
        return;
    }
    
    container.innerHTML = urgentTasks.slice(0, 5).map(task => renderTaskItem(task)).join('');
}

function renderWorkspaces(workspaces) {
    const container = document.getElementById('workspaces-list');
    
    container.innerHTML = workspaces.map(ws => {
        const icon = ws.is_personal ? '🏠' : '👥';
        return `
            <div class="workspace-item" onclick="switchWorkspace(${ws.id})">
                <span class="workspace-icon">${icon}</span>
                <div class="workspace-info">
                    <div class="workspace-name">${escapeHtml(ws.name)}</div>
                    <div class="workspace-count">${ws.role === 'owner' ? 'Владелец' : 'Участник'}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ==================== КАЛЕНДАРЬ ====================

function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    const monthLabel = document.getElementById('cal-month');
    
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
    monthLabel.textContent = `${monthNames[month]} ${year}`;
    
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    
    let startDay = firstDay.getDay();
    startDay = startDay === 0 ? 6 : startDay - 1;
    
    const prevMonthLastDay = new Date(year, month, 0).getDate();
    
    let html = '';
    
    for (let i = startDay - 1; i >= 0; i--) {
        const day = prevMonthLastDay - i;
        html += `<div class="calendar-day other-month">${day}</div>`;
    }
    
    const today = new Date();
    
    for (let day = 1; day <= lastDay.getDate(); day++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const isToday = today.getDate() === day && today.getMonth() === month && today.getFullYear() === year;
        
        const hasTasks = allTasks.some(t => {
            const taskDate = new Date(t.created_at);
            return taskDate.getDate() === day && taskDate.getMonth() === month && taskDate.getFullYear() === year;
        });
        
        const classes = ['calendar-day'];
        if (isToday) classes.push('today');
        if (hasTasks) classes.push('has-tasks');
        if (selectedDate === dateStr) classes.push('selected');
        
        html += `<div class="${classes.join(' ')}" onclick="selectDate('${dateStr}', ${day})">${day}</div>`;
    }
    
    const totalCells = startDay + lastDay.getDate();
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    
    for (let i = 1; i <= remainingCells; i++) {
        html += `<div class="calendar-day other-month">${i}</div>`;
    }
    
    grid.innerHTML = html;
}

function prevMonth() {
    currentDate.setMonth(currentDate.getMonth() - 1);
    renderCalendar();
    haptic('light');
}

function nextMonth() {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
    haptic('light');
}

function selectDate(dateStr, day) {
    selectedDate = dateStr;
    renderCalendar();
    
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    const dayTasks = allTasks.filter(t => {
        const taskDate = new Date(t.created_at);
        return taskDate.getDate() === day && taskDate.getMonth() === month && taskDate.getFullYear() === year;
    });
    
    const monthNames = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 
                        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    
    document.getElementById('selected-date-title').textContent = `📅 ${day} ${monthNames[month]}`;
    
    const container = document.getElementById('calendar-task-list');
    
    if (dayTasks.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">📭</span><span>Нет задач на этот день</span></div>';
    } else {
        container.innerHTML = dayTasks.map(task => renderTaskItem(task)).join('');
    }
    
    haptic('light');
}

// ==================== ДОСТИЖЕНИЯ ====================

function updateAchievements(doneCount) {
    const achievements = document.querySelectorAll('.achievement');
    const thresholds = [1, 5, 10, 50, 100, 7];
    
    achievements.forEach((ach, index) => {
        if (index < 5) {
            if (doneCount >= thresholds[index]) {
                ach.classList.remove('locked');
                ach.classList.add('unlocked');
            }
        }
    });
}

// ==================== НАВИГАЦИЯ ====================

function switchPage(pageName) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${pageName}`).classList.add('active');
    
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.page === pageName);
    });
    
    const titles = {
        home: 'Моя CRM',
        tasks: 'Задачи',
        calendar: 'Календарь',
        profile: 'Профиль'
    };
    document.getElementById('page-title').textContent = titles[pageName] || 'CRM';
    
    const fab = document.querySelector('.fab');
    fab.style.display = pageName === 'profile' ? 'none' : 'flex';
    
    haptic('light');
}

async function switchWorkspace(workspaceId) {
    currentWorkspaceId = workspaceId;
    await loadWorkspace(workspaceId);
    switchPage('tasks');
    showToast('✅ Пространство выбрано');
}

// ==================== ОБРАБОТЧИКИ СОБЫТИЙ ====================

function setupEventListeners() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const view = tab.dataset.view;
            
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.getElementById(`view-${view}`).classList.add('active');
            
            haptic('light');
        });
    });
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            currentFilter = btn.dataset.filter;
            
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            renderTaskList(allTasks);
            haptic('light');
        });
    });
    
    document.querySelectorAll('.priority-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            selectedPriority = btn.dataset.priority;
            haptic('light');
        });
    });
}

// ==================== МОДАЛЬНЫЕ ОКНА ====================

function showAddTask() {
    isEditing = false;
    currentTask = null;
    
    document.getElementById('task-title').value = '';
    document.getElementById('task-desc').value = '';
    document.getElementById('task-due').value = '';
    
    document.getElementById('modal-add-title').textContent = '➕ Новая задача';
    document.getElementById('modal-add-btn').textContent = '✨ Создать';
    
    selectedPriority = 'medium';
    document.querySelectorAll('.priority-btn').forEach(b => {
        b.classList.toggle('selected', b.dataset.priority === 'medium');
    });
    
    openModal('modal-add');
}

function editTask(taskId) {
    const task = allTasks.find(t => t.id === taskId);
    if (!task) return;
    
    isEditing = true;
    currentTask = task;
    
    document.getElementById('task-title').value = task.title;
    document.getElementById('task-desc').value = task.description || '';
    document.getElementById('task-due').value = task.due_date ? task.due_date.split('T')[0] : '';
    
    document.getElementById('modal-add-title').textContent = '✏️ Редактировать';
    document.getElementById('modal-add-btn').textContent = '💾 Сохранить';
    
    selectedPriority = task.priority || 'medium';
    document.querySelectorAll('.priority-btn').forEach(b => {
        b.classList.toggle('selected', b.dataset.priority === selectedPriority);
    });
    
    openModal('modal-add');
    haptic('light');
}

function showTask(taskId) {
    const task = allTasks.find(t => t.id === taskId);
    if (!task) return;
    
    currentTask = task;
    
    document.getElementById('view-task-title').textContent = task.title;
    document.getElementById('view-task-desc').textContent = task.description || 'Без описания';
    
    const modalPriority = document.getElementById('modal-priority');
    modalPriority.className = 'modal-task-priority ' + task.priority;
    
    const priorityTexts = { high: '🔴 Высокий', medium: '🟡 Средний', low: '🟢 Низкий' };
    document.getElementById('view-task-priority-text').textContent = priorityTexts[task.priority] || 'Средний';
    
    const statusEl = document.getElementById('view-task-status');
    statusEl.textContent = task.status === 'done' ? 'Выполнена' : 'В работе';
    statusEl.className = 'task-status ' + (task.status === 'done' ? 'done' : 'todo');
    
    document.getElementById('view-task-date').textContent = formatDateFull(task.created_at);
    
    document.getElementById('toggle-btn-text').textContent = task.status === 'done' ? 'Открыть' : 'Выполнено';
    
    openModal('modal-task');
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
    haptic('light');
}

function closeModal() {
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
    currentTask = null;
    isEditing = false;
}

// ==================== ДЕЙСТВИЯ С ЗАДАЧАМИ ====================

async function saveTask() {
    const title = document.getElementById('task-title').value.trim();
    const description = document.getElementById('task-desc').value.trim();
    const dueDate = document.getElementById('task-due').value;
    
    if (!title) {
        showToast('⚠️ Введите название', 'warning');
        document.getElementById('task-title').focus();
        return;
    }
    
    try {
        let response;
        
        if (isEditing && currentTask) {
            // Редактирование
            response = await fetch(`/api/task/${currentTask.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    description: description || null,
                    priority: selectedPriority
                })
            });
            
            if (response.ok) {
                closeModal();
                await loadUserData();
                showToast('✅ Задача обновлена!');
                haptic('success');
            }
        } else {
            // Создание
            response = await fetch(`/api/tasks/${currentWorkspaceId}/${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    description: description || null,
                    priority: selectedPriority
                })
            });
            
            if (response.ok) {
                closeModal();
                await loadUserData();
                showToast('✅ Задача создана!');
                haptic('success');
            }
        }
        
        if (!response.ok) {
            showToast('❌ Ошибка сохранения', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('❌ Ошибка сети', 'error');
    }
}

// Для совместимости со старым кодом
async function createTask() {
    await saveTask();
}

async function toggleTask(taskId) {
    try {
        const response = await fetch(`/api/task/${taskId}/toggle`, { method: 'POST' });
        
        if (response.ok) {
            const data = await response.json();
            const isDone = data.task.status === 'done';
            
            await loadUserData();
            
            showToast(isDone ? '✅ Выполнено!' : '🔄 Открыто');
            haptic(isDone ? 'success' : 'light');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('❌ Ошибка', 'error');
    }
}

async function toggleCurrentTask() {
    if (currentTask) {
        await toggleTask(currentTask.id);
        closeModal();
    }
}

function editCurrentTask() {
    if (!currentTask) return;
    closeModal();
    editTask(currentTask.id);
}

function confirmDeleteTask(taskId) {
    const task = allTasks.find(t => t.id === taskId);
    if (!task) return;
    
    currentTask = task;
    
    document.getElementById('delete-task-title').textContent = task.title;
    openModal('modal-delete');
}

async function deleteTask(taskId) {
    try {
        const response = await fetch(`/api/task/${taskId}`, { method: 'DELETE' });
        
        if (response.ok) {
            closeModal();
            await loadUserData();
            showToast('🗑 Задача удалена');
            haptic('warning');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('❌ Ошибка', 'error');
    }
}

async function confirmDelete() {
    if (currentTask) {
        await deleteTask(currentTask.id);
    }
}

async function deleteCurrentTask() {
    if (!currentTask) return;
    confirmDeleteTask(currentTask.id);
}

// ==================== ТЕМА ====================

function toggleTheme() {
    document.body.classList.toggle('light-theme');
    const isLight = document.body.classList.contains('light-theme');
    document.querySelector('.theme-toggle').textContent = isLight ? '☀️' : '🌙';
    
    const themeToggle = document.getElementById('theme-toggle-btn');
    if (themeToggle) {
        themeToggle.classList.toggle('active', !isLight);
    }
    
    haptic('light');
}

// ==================== УТИЛИТЫ ====================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Только что';
    if (diff < 3600000) return Math.floor(diff / 60000) + ' мин назад';
    if (diff < 86400000) return 'Сегодня';
    if (diff < 172800000) return 'Вчера';
    
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function formatDateFull(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', { 
        day: 'numeric', 
        month: 'long', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function haptic(type) {
    if (tg?.HapticFeedback) {
        if (type === 'success') {
            tg.HapticFeedback.notificationOccurred('success');
        } else if (type === 'warning') {
            tg.HapticFeedback.notificationOccurred('warning');
        } else if (type === 'error') {
            tg.HapticFeedback.notificationOccurred('error');
        } else {
            tg.HapticFeedback.impactOccurred('light');
        }
    }
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const icon = toast.querySelector('.toast-icon');
    const text = toast.querySelector('.toast-text');
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️'
    };
    
    icon.textContent = icons[type] || '✅';
    text.textContent = message;
    
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2500);
}

function showLoading(show) {
    // Можно добавить индикатор загрузки
}

// ==================== ЗАКРЫТИЕ МОДАЛОК ====================

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        closeModal();
    }
});

let touchStartY = 0;
document.addEventListener('touchstart', (e) => {
    touchStartY = e.touches[0].clientY;
});

document.addEventListener('touchend', (e) => {
    const touchEndY = e.changedTouches[0].clientY;
    const diff = touchEndY - touchStartY;
    
    if (diff > 100) {
        const activeModal = document.querySelector('.modal.active');
        if (activeModal) {
            closeModal();
        }
    }
});
