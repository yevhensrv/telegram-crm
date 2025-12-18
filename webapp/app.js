// ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================

const tg = window.Telegram?.WebApp;
let userId = null;
let userData = null;
let currentWorkspaceId = null;
let currentTask = null;
let allTasks = [];
let allMembers = [];
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
        const response = await fetch(`/api/user/${userId}`);
        if (!response.ok) return;
        
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
    }
}

async function loadWorkspace(workspaceId) {
    try {
        const response = await fetch(`/api/workspace/${workspaceId}`);
        if (!response.ok) return;
        
        const data = await response.json();
        allTasks = data.tasks || [];
        allMembers = data.members || [];
        
        renderBoard(data.funnels);
        renderTaskList(allTasks);
        renderTodayTasks();
        renderUrgentTasks();
        renderCalendar();
        renderMembers();
        
    } catch (error) {
        console.error('Error loading workspace:', error);
    }
}

// ==================== СТАТИСТИКА ====================

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

// ==================== РЕНДЕРИНГ ЗАДАЧ ====================

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
            <div class="column-tasks">
                ${stage.tasks.map(task => renderTaskCard(task)).join('')}
            </div>
        `;
        board.appendChild(column);
    });
}

function renderTaskCard(task) {
    const isDone = task.status === 'done';
    const assignee = task.assigned_username ? `@${task.assigned_username}` : '';
    const dueDate = task.due_date ? formatDueDate(task.due_date) : '';
    
    return `
        <div class="task-card ${isDone ? 'done' : ''} priority-${task.priority}" onclick="showTask(${task.id})">
            <div class="task-card-title">${escapeHtml(task.title)}</div>
            <div class="task-card-meta">
                ${dueDate ? `<span class="task-due">📅 ${dueDate}</span>` : ''}
                ${assignee ? `<span class="task-assignee">👤 ${assignee}</span>` : ''}
            </div>
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
    const assignee = task.assigned_username ? `@${task.assigned_username}` : '';
    const dueDate = task.due_date ? formatDueDate(task.due_date) : '';
    
    return `
        <div class="task-item ${isDone ? 'done' : ''} priority-${task.priority}" onclick="showTask(${task.id})">
            <div class="task-checkbox" onclick="event.stopPropagation(); toggleTask(${task.id})"></div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title)}</div>
                <div class="task-meta">
                    ${dueDate ? `<span class="task-meta-item">📅 ${dueDate}</span>` : ''}
                    ${assignee ? `<span class="task-meta-item">👤 ${assignee}</span>` : ''}
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
    const today = new Date().toISOString().split('T')[0];
    
    const todayTasks = allTasks.filter(t => {
        return (t.due_date === today || new Date(t.created_at).toDateString() === new Date().toDateString()) 
               && t.status !== 'done';
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
        const role = ws.custom_role || ws.role;
        return `
            <div class="workspace-item" onclick="switchWorkspace(${ws.id})">
                <span class="workspace-icon">${icon}</span>
                <div class="workspace-info">
                    <div class="workspace-name">${escapeHtml(ws.name)}</div>
                    <div class="workspace-count">${role === 'owner' ? 'Владелец' : role}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ==================== РЕНДЕРИНГ УЧАСТНИКОВ ====================

function renderMembers() {
    const container = document.getElementById('members-list');
    if (!container) return;
    
    if (!allMembers || allMembers.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">👥</span><span>Нет участников</span></div>';
        return;
    }
    
    container.innerHTML = allMembers.map(member => {
        const roleText = member.custom_role || getRoleName(member.role);
        const isOwner = member.role === 'owner';
        
        return `
            <div class="member-item">
                <div class="member-avatar">👤</div>
                <div class="member-info">
                    <div class="member-name">${escapeHtml(member.full_name || 'Пользователь')}</div>
                    <div class="member-username">@${member.username || 'unknown'}</div>
                    <div class="member-role">${roleText}</div>
                </div>
                ${!isOwner ? `
                    <div class="member-actions">
                        <button class="mini-btn" onclick="editMember(${member.id})">⚙️</button>
                        <button class="mini-btn delete" onclick="confirmRemoveMember(${member.id})">✕</button>
                    </div>
                ` : '<span class="owner-badge">👑</span>'}
            </div>
        `;
    }).join('');
}

function getRoleName(role) {
    const roles = {
        'owner': 'Владелец',
        'pm': 'PM',
        'lead': 'НП',
        'team_lead': 'СК',
        'admin': 'Админ',
        'member': 'Участник'
    };
    return roles[role] || role;
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
        html += `<div class="calendar-day other-month">${prevMonthLastDay - i}</div>`;
    }
    
    const today = new Date();
    
    for (let day = 1; day <= lastDay.getDate(); day++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const isToday = today.getDate() === day && today.getMonth() === month && today.getFullYear() === year;
        
        const hasTasks = allTasks.some(t => t.due_date === dateStr);
        
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
}

function nextMonth() {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
}

function selectDate(dateStr, day) {
    selectedDate = dateStr;
    renderCalendar();
    
    const dayTasks = allTasks.filter(t => t.due_date === dateStr);
    
    const monthNames = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 
                        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    
    document.getElementById('selected-date-title').textContent = `📅 ${day} ${monthNames[currentDate.getMonth()]}`;
    
    const container = document.getElementById('calendar-task-list');
    
    if (dayTasks.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">📭</span><span>Нет задач на этот день</span></div>';
    } else {
        container.innerHTML = dayTasks.map(task => renderTaskItem(task)).join('');
    }
}

// ==================== ДОСТИЖЕНИЯ ====================

function updateAchievements(doneCount) {
    const achievements = document.querySelectorAll('.achievement');
    const thresholds = [1, 5, 10, 50, 100, 7];
    
    achievements.forEach((ach, index) => {
        if (index < 5 && doneCount >= thresholds[index]) {
            ach.classList.remove('locked');
            ach.classList.add('unlocked');
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
    
    const titles = { home: 'Моя CRM', tasks: 'Задачи', calendar: 'Календарь', profile: 'Профиль' };
    document.getElementById('page-title').textContent = titles[pageName] || 'CRM';
    
    document.querySelector('.fab').style.display = pageName === 'profile' ? 'none' : 'flex';
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
        });
    });
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            currentFilter = btn.dataset.filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderTaskList(allTasks);
        });
    });
    
    document.querySelectorAll('.priority-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            selectedPriority = btn.dataset.priority;
        });
    });
}

// ==================== МОДАЛЬНЫЕ ОКНА ====================

function showAddTask() {
    isEditing = false;
    currentTask = null;
    
    document.getElementById('task-title').value = '';
    document.getElementById('task-desc').value = '';
    document.getElementById('task-due-date').value = '';
    document.getElementById('task-due-time').value = '';
    document.getElementById('task-assignee').value = '';
    
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
    
    document.getElementById('task-title').value = task.title || '';
    document.getElementById('task-desc').value = task.description || '';
    document.getElementById('task-due-date').value = task.due_date || '';
    document.getElementById('task-due-time').value = task.due_time || '';
    document.getElementById('task-assignee').value = task.assigned_username ? `@${task.assigned_username}` : '';
    
    document.getElementById('modal-add-title').textContent = '✏️ Редактировать';
    document.getElementById('modal-add-btn').textContent = '💾 Сохранить';
    
    selectedPriority = task.priority || 'medium';
    document.querySelectorAll('.priority-btn').forEach(b => {
        b.classList.toggle('selected', b.dataset.priority === selectedPriority);
    });
    
    openModal('modal-add');
}

function showTask(taskId) {
    const task = allTasks.find(t => t.id === taskId);
    if (!task) return;
    
    currentTask = task;
    
    document.getElementById('view-task-title').textContent = task.title;
    document.getElementById('view-task-desc').textContent = task.description || 'Без описания';
    
    document.getElementById('modal-priority').className = 'modal-task-priority ' + task.priority;
    
    const priorityTexts = { high: '🔴 Высокий', medium: '🟡 Средний', low: '🟢 Низкий' };
    document.getElementById('view-task-priority-text').textContent = priorityTexts[task.priority] || 'Средний';
    
    const statusEl = document.getElementById('view-task-status');
    statusEl.textContent = task.status === 'done' ? 'Выполнена' : 'В работе';
    statusEl.className = 'task-status ' + (task.status === 'done' ? 'done' : 'todo');
    
    document.getElementById('view-task-date').textContent = formatDateFull(task.created_at);
    
    // Дедлайн
    const dueEl = document.getElementById('view-task-due');
    if (dueEl) {
        dueEl.textContent = task.due_date ? `${formatDueDate(task.due_date)} ${task.due_time || ''}` : 'Не указан';
    }
    
    // Исполнитель
    const assigneeEl = document.getElementById('view-task-assignee');
    if (assigneeEl) {
        assigneeEl.textContent = task.assigned_username ? `@${task.assigned_username}` : 'Не назначен';
    }
    
    document.getElementById('toggle-btn-text').textContent = task.status === 'done' ? 'Открыть' : 'Выполнено';
    
    openModal('modal-task');
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
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
    const dueDate = document.getElementById('task-due-date').value;
    const dueTime = document.getElementById('task-due-time').value;
    const assignee = document.getElementById('task-assignee').value.trim();
    
    if (!title) {
        showToast('⚠️ Введите название', 'warning');
        return;
    }
    
    try {
        let response;
        
        if (isEditing && currentTask) {
            response = await fetch(`/api/task/${currentTask.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    description: description || null,
                    priority: selectedPriority,
                    due_date: dueDate || null,
                    due_time: dueTime || null,
                    assigned_username: assignee || null
                })
            });
        } else {
            response = await fetch(`/api/tasks/${currentWorkspaceId}/${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    description: description || null,
                    priority: selectedPriority,
                    due_date: dueDate || null,
                    due_time: dueTime || null,
                    assigned_username: assignee || null
                })
            });
        }
        
        if (response.ok) {
            closeModal();
            await loadUserData();
            showToast(isEditing ? '✅ Задача обновлена!' : '✅ Задача создана!');
        } else {
            const error = await response.json();
            showToast(`❌ ${error.detail || 'Ошибка'}`, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('❌ Ошибка сети', 'error');
    }
}

async function toggleTask(taskId) {
    try {
        const response = await fetch(`/api/task/${taskId}/toggle`, { method: 'POST' });
        if (response.ok) {
            await loadUserData();
            showToast('✅ Статус изменён');
        }
    } catch (error) {
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

async function confirmDelete() {
    if (!currentTask) return;
    
    try {
        const response = await fetch(`/api/task/${currentTask.id}`, { method: 'DELETE' });
        if (response.ok) {
            closeModal();
            await loadUserData();
            showToast('🗑 Задача удалена');
        }
    } catch (error) {
        showToast('❌ Ошибка', 'error');
    }
}

async function deleteCurrentTask() {
    if (!currentTask) return;
    confirmDeleteTask(currentTask.id);
}

// ==================== УЧАСТНИКИ ====================

function showAddMember() {
    document.getElementById('member-username').value = '';
    document.getElementById('member-role').value = 'member';
    document.getElementById('member-custom-role').value = '';
    openModal('modal-add-member');
}

async function saveMember() {
    const username = document.getElementById('member-username').value.trim().replace('@', '');
    const role = document.getElementById('member-role').value;
    const customRole = document.getElementById('member-custom-role').value.trim();
    
    if (!username) {
        showToast('⚠️ Введите @username', 'warning');
        return;
    }
    
    // Получаем права из выбранной роли
    let permissions = {
        can_edit_tasks: true,
        can_delete_tasks: false,
        can_assign_tasks: false,
        can_manage_members: false
    };
    
    if (role === 'pm' || role === 'lead' || role === 'team_lead') {
        permissions = { can_edit_tasks: true, can_delete_tasks: true, can_assign_tasks: true, can_manage_members: true };
    } else if (role === 'admin') {
        permissions = { can_edit_tasks: true, can_delete_tasks: false, can_assign_tasks: true, can_manage_members: true };
    }
    
    try {
        const response = await fetch(`/api/workspace/${currentWorkspaceId}/members`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                role,
                custom_role: customRole || null,
                ...permissions
            })
        });
        
        if (response.ok) {
            closeModal();
            await loadWorkspace(currentWorkspaceId);
            showToast('✅ Участник добавлен!');
        } else {
            const error = await response.json();
            showToast(`❌ ${error.detail}`, 'error');
        }
    } catch (error) {
        showToast('❌ Ошибка сети', 'error');
    }
}

function confirmRemoveMember(userId) {
    if (confirm('Удалить участника из команды?')) {
        removeMember(userId);
    }
}

async function removeMember(memberId) {
    try {
        const response = await fetch(`/api/workspace/${currentWorkspaceId}/members/${memberId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            await loadWorkspace(currentWorkspaceId);
            showToast('✅ Участник удалён');
        }
    } catch (error) {
        showToast('❌ Ошибка', 'error');
    }
}

// ==================== ТЕМА ====================

function toggleTheme() {
    document.body.classList.toggle('light-theme');
    const isLight = document.body.classList.contains('light-theme');
    document.querySelector('.theme-toggle').textContent = isLight ? '☀️' : '🌙';
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
        day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
}

function formatDueDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const today = new Date();
    
    if (date.toDateString() === today.toDateString()) return 'Сегодня';
    
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (date.toDateString() === tomorrow.toDateString()) return 'Завтра';
    
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const icons = { success: '✅', error: '❌', warning: '⚠️' };
    
    toast.querySelector('.toast-icon').textContent = icons[type] || '✅';
    toast.querySelector('.toast-text').textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => toast.classList.remove('show'), 2500);
}

// Закрытие модалок
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) closeModal();
});
