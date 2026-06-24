"""
Программное средство для систематизации и учета проектных работ
Полная реализация ТЗ с отдельными HTML шаблонами
"""

import os
import json
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import pandas as pd

from config import Config
from models import db, User, UserRole, ProjectType, ProjectStatus, TaskStatus, Customer, Project, ProjectStage, Task, TimeEntry, DocumentType, Document, WorkAct

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== ДЕКОРАТОРЫ ДОСТУПА ==========

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_manager() or current_user.is_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def allowed_file(filename, doc_type):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in Config.ALLOWED_EXTENSIONS.get(doc_type, [])

def generate_project_code():
    year = datetime.now().year
    last = Project.query.filter(Project.ProjectCode.like(f'PRJ-{year}-%')).order_by(Project.ProjectID.desc()).first()
    num = int(last.ProjectCode.split('-')[-1]) + 1 if last else 1
    return f'PRJ-{year}-{num:03d}'

# ========== ГЛАВНЫЕ МАРШРУТЫ ==========

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember_me', False)
        
        user = User.query.filter_by(Username=username, IsActive=True).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.LastLoginAt = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        
        flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    stats = {}
    
    if current_user.is_admin():
        stats['total_projects'] = Project.query.count()
        stats['active_projects'] = Project.query.filter_by(StatusID=2).count()
        stats['total_users'] = User.query.filter_by(IsActive=True).count()
        stats['total_customers'] = Customer.query.filter_by(IsActive=True).count()
    elif current_user.is_manager():
        stats['my_projects'] = Project.query.filter_by(ManagerID=current_user.UserID).count()
        stats['active_projects'] = Project.query.filter_by(ManagerID=current_user.UserID, StatusID=2).count()
        stats['overdue'] = Project.query.filter(Project.ManagerID==current_user.UserID, 
                                                 Project.PlannedEndDate < date.today(),
                                                 Project.StatusID != 4).count()
    else:
        stats['my_tasks'] = Task.query.filter_by(AssignedTo=current_user.UserID).count()
        stats['pending_tasks'] = Task.query.filter_by(AssignedTo=current_user.UserID, StatusID=1).count()
        stats['completed_tasks'] = Task.query.filter_by(AssignedTo=current_user.UserID, StatusID=5).count()
    
    return render_template('dashboard.html', stats=stats)

# ========== АДМИНИСТРАТОР ==========

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    roles = UserRole.query.all()
    return render_template('admin/users.html', users=users, roles=roles)

@app.route('/admin/users/add', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    user = User(
        Username=request.form.get('username'),
        Email=request.form.get('email'),
        FullName=request.form.get('full_name'),
        RoleID=request.form.get('role_id'),
        Department=request.form.get('department'),
        Position=request.form.get('position'),
        IsActive=True
    )
    user.PasswordHash = generate_password_hash(request.form.get('password'))
    user.Salt = 'salt'
    
    db.session.add(user)
    db.session.commit()
    flash('Пользователь создан', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/classifiers')
@login_required
@admin_required
def admin_classifiers():
    types = ProjectType.query.all()
    statuses = ProjectStatus.query.all()
    return render_template('admin/classifiers.html', types=types, statuses=statuses)

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    roles = UserRole.query.all()
    
    if request.method == 'POST':
        user.FullName = request.form.get('full_name')
        user.Email = request.form.get('email')
        user.Username = request.form.get('username')
        user.RoleID = request.form.get('role_id')
        user.Department = request.form.get('department')
        user.Position = request.form.get('position')
        user.IsActive = request.form.get('is_active') == 'on'
        
        # Обновляем пароль только если введен новый
        new_password = request.form.get('password')
        if new_password:
            user.PasswordHash = generate_password_hash(new_password)
        
        db.session.commit()
        flash('Пользователь обновлен', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', user=user, roles=roles)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Нельзя удалить самого себя
    if user.UserID == current_user.UserID:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('admin_users'))
    
    # Проверяем, есть ли у пользователя задачи
    assigned_tasks = Task.query.filter_by(AssignedTo=user.UserID).count()
    if assigned_tasks > 0:
        flash(f'Нельзя удалить: у пользователя {assigned_tasks} назначенных задач. Сначала переназначьте задачи.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Проверяем, есть ли у пользователя записи времени
    time_entries = TimeEntry.query.filter_by(UserID=user.UserID).count()
    if time_entries > 0:
        flash(f'Нельзя удалить: у пользователя {time_entries} записей рабочего времени.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Проверяем, управляет ли пользователь проектами
    managed_projects = Project.query.filter_by(ManagerID=user.UserID).count()
    if managed_projects > 0:
        flash(f'Нельзя удалить: пользователь управляет {managed_projects} проектами. Сначала смените менеджера.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Проверяем, создал ли пользователь задачи
    created_tasks = Task.query.filter_by(CreatedBy=user.UserID).count()
    if created_tasks > 0:
        flash(f'Нельзя удалить: пользователь создал {created_tasks} задач.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Если всё чисто - удаляем
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удален', 'success')
    return redirect(url_for('admin_users'))

# ========== РУКОВОДИТЕЛЬ ПРОЕКТОВ ==========

@app.route('/projects')
@login_required
@manager_required
def projects_list():
    status_id = request.args.get('status', type=int)
    type_id = request.args.get('type', type=int)
    search = request.args.get('search', '')
    
    query = Project.query
    
    if status_id:
        query = query.filter_by(StatusID=status_id)
    if type_id:
        query = query.filter_by(TypeID=type_id)
    if search:
        query = query.filter(Project.ProjectName.contains(search))
    
    if current_user.is_manager():
        query = query.filter_by(ManagerID=current_user.UserID)
    
    projects = query.order_by(Project.CreatedAt.desc()).all()
    statuses = ProjectStatus.query.all()
    types = ProjectType.query.all()
    
    return render_template('manager/projects.html', projects=projects, statuses=statuses, types=types)

@app.route('/projects/create', methods=['GET', 'POST'])
@login_required
@manager_required
def project_create():
    if request.method == 'POST':
        project = Project(
            ProjectCode=generate_project_code(),
            ProjectName=request.form.get('name'),
            TypeID=request.form.get('type_id'),
            CustomerID=request.form.get('customer_id'),
            StatusID=1,
            ManagerID=current_user.UserID,
            Description=request.form.get('description'),
            StartDate=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d'),
            PlannedEndDate=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d'),
            Budget=request.form.get('budget') or 0,
            Priority=request.form.get('priority', 3)
        )
        db.session.add(project)
        db.session.commit()
        flash('Проект создан', 'success')
        return redirect(url_for('projects_list'))
    
    types = ProjectType.query.all()
    customers = Customer.query.filter_by(IsActive=True).all()
    return render_template('manager/project_create.html', types=types, customers=customers)

@app.route('/projects/<int:project_id>')
@login_required
@manager_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    
    if current_user.is_manager() and project.ManagerID != current_user.UserID:
        abort(403)
    
    stages = ProjectStage.query.filter_by(ProjectID=project_id).all()
    tasks = Task.query.filter_by(ProjectID=project_id).all()
    documents = Document.query.filter_by(ProjectID=project_id).all()
    
    return render_template('manager/project_detail.html', project=project, stages=stages, tasks=tasks, documents=documents)

@app.route('/projects/<int:project_id>/tasks/create', methods=['GET', 'POST'])
@login_required
@manager_required
def task_create(project_id):
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        task = Task(
            ProjectID=project_id,
            TaskName=request.form.get('name'),
            Description=request.form.get('description'),
            AssignedTo=request.form.get('assigned_to'),
            CreatedBy=current_user.UserID,
            StatusID=1,
            PlannedHours=request.form.get('planned_hours'),
            DueDate=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d'),
            Priority=request.form.get('priority', 3)
        )
        db.session.add(task)
        db.session.commit()
        flash('Задача создана', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    
    employees = User.query.filter_by(RoleID=3).all()
    return render_template('manager/task_create.html', project=project, employees=employees)

@app.route('/workload')
@login_required
@manager_required
def workload():
    employees = User.query.filter_by(RoleID=3).all()
    workload_data = []
    
    for emp in employees:
        tasks = Task.query.filter_by(AssignedTo=emp.UserID).all()
        total_planned = sum([float(t.PlannedHours or 0) for t in tasks])
        total_actual = sum([float(t.ActualHours or 0) for t in tasks])
        pending = len([t for t in tasks if t.StatusID != 5])
        completed = len([t for t in tasks if t.StatusID == 5])
        
        workload_data.append({
            'employee': emp,
            'tasks_total': len(tasks),
            'pending': pending,
            'completed': completed,
            'planned_hours': total_planned,
            'actual_hours': total_actual,
            'efficiency': (total_actual / total_planned * 100) if total_planned > 0 else 0
        })
    
    return render_template('manager/workload.html', workload_data=workload_data)

@app.route('/acts')
@login_required
@manager_required
def acts_list():
    # Админ видит все акты, менеджер - только свои проекты
    if current_user.is_admin():
        acts = WorkAct.query.order_by(WorkAct.ActDate.desc()).all()
    else:
        acts = WorkAct.query.join(Project).filter(Project.ManagerID == current_user.UserID).order_by(WorkAct.ActDate.desc()).all()
    
    return render_template('manager/acts.html', acts=acts)

@app.route('/acts/create', methods=['GET', 'POST'])
@login_required
@manager_required
def act_create():
    if request.method == 'POST':
        year = datetime.now().year
        last = WorkAct.query.filter(WorkAct.ActNumber.like(f'ACT-{year}-%')).order_by(WorkAct.ActID.desc()).first()
        num = int(last.ActNumber.split('-')[-1]) + 1 if last else 1
        
        act = WorkAct(
            ActNumber=f'ACT-{year}-{num:03d}',
            ProjectID=request.form.get('project_id'),
            ActDate=date.today(),
            PeriodStart=datetime.strptime(request.form.get('period_start'), '%Y-%m-%d'),
            PeriodEnd=datetime.strptime(request.form.get('period_end'), '%Y-%m-%d'),
            TotalHours=0,
            CreatedBy=current_user.UserID
        )
        db.session.add(act)
        db.session.commit()
        flash('Акт создан', 'success')
        return redirect(url_for('acts_list'))
    
    projects = Project.query.filter_by(ManagerID=current_user.UserID).all()
    return render_template('manager/act_create.html', projects=projects)

@app.route('/acts/<int:act_id>/approve', methods=['POST'])
@login_required
@manager_required
def act_approve(act_id):
    act = WorkAct.query.get_or_404(act_id)
    act.Status = 'approved'
    db.session.commit()
    flash('Акт утверждён', 'success')
    return redirect(url_for('acts_list'))

@app.route('/acts/<int:act_id>/sign', methods=['POST'])
@login_required
@manager_required
def act_sign(act_id):
    act = WorkAct.query.get_or_404(act_id)
    act.Status = 'signed'
    act.SignedByCustomer = True
    act.SignedDate = date.today()
    db.session.commit()
    flash('Акт подписан заказчиком', 'success')
    return redirect(url_for('acts_list'))

@app.route('/projects/<int:project_id>/upload', methods=['GET', 'POST'])
@login_required
@manager_required
def project_upload(project_id):
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран', 'danger')
            return redirect(url_for('project_upload', project_id=project_id))
        
        file = request.files['file']
        if not file or file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(url_for('project_upload', project_id=project_id))
        
        if '.' not in file.filename:
            flash('Файл должен иметь расширение', 'danger')
            return redirect(url_for('project_upload', project_id=project_id))
        
        filename = secure_filename(file.filename)
        parts = filename.rsplit('.', 1)
        if len(parts) < 2:
            flash('Неверное имя файла', 'danger')
            return redirect(url_for('project_upload', project_id=project_id))
        
        ext = parts[1].lower()
        
        # Создаём папку если нет
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Определяем тип документа
        doc_type = DocumentType.query.filter(DocumentType.AllowedExtensions.contains(ext)).first()
        
        doc = Document(
            ProjectID=project_id,
            DocTypeID=doc_type.DocTypeID if doc_type else 6,
            DocumentName=request.form.get('name') or filename,
            FileName=filename,
            FilePath=filepath,
            FileSize=os.path.getsize(filepath),
            UploadedBy=current_user.UserID
        )
        db.session.add(doc)
        db.session.commit()
        
        flash('Файл загружен успешно', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    
    return render_template('manager/project_upload.html', project=project)

@app.route('/download/<int:document_id>')
@login_required
def download_file(document_id):
    doc = Document.query.get_or_404(document_id)
    
    # Проверка доступа: только участники проекта или админ
    if not (current_user.is_admin() or 
            current_user.UserID == doc.UploadedBy or
            (doc.project and doc.project.ManagerID == current_user.UserID) or
            (doc.task and doc.task.AssignedTo == current_user.UserID)):
        abort(403)
    
    if not os.path.exists(doc.FilePath):
        flash('Файл не найден на сервере', 'danger')
        return redirect(url_for('project_detail', project_id=doc.ProjectID))
    
    return send_file(doc.FilePath, as_attachment=True, download_name=doc.FileName)

# ========== СОТРУДНИК ==========

@app.route('/my-tasks')
@login_required
def my_tasks():
    status_filter = request.args.get('status', type=int)
    
    query = Task.query.filter_by(AssignedTo=current_user.UserID)
    if status_filter:
        query = query.filter_by(StatusID=status_filter)
    
    tasks = query.order_by(Task.DueDate).all()
    statuses = TaskStatus.query.all()
    return render_template('employee/tasks.html', tasks=tasks, statuses=statuses, date=date)

@app.route('/tasks/<int:task_id>/update', methods=['GET', 'POST'])
@login_required
def task_update(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.AssignedTo != current_user.UserID and not current_user.is_manager():
        abort(403)
    
    if request.method == 'POST':
        task.StatusID = request.form.get('status_id')
        if request.form.get('actual_hours'):
            task.ActualHours = request.form.get('actual_hours')
        
        if int(request.form.get('status_id')) == 5:
            task.CompletedAt = datetime.utcnow()
        
        db.session.commit()
        flash('Задача обновлена', 'success')
        return redirect(url_for('my_tasks'))
    
    statuses = TaskStatus.query.all()
    return render_template('employee/task_update.html', task=task, statuses=statuses)

@app.route('/tasks/<int:task_id>/upload', methods=['POST'])
@login_required
def task_upload(task_id):
    task = Task.query.get_or_404(task_id)
    
    if 'file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('task_update', task_id=task_id))
    
    file = request.files['file']
    if not file or file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('task_update', task_id=task_id))
    
    filename = secure_filename(file.filename)
    
    # Проверяем расширение
    if '.' not in filename:
        flash('Файл должен иметь расширение', 'danger')
        return redirect(url_for('task_update', task_id=task_id))
    
    parts = filename.rsplit('.', 1)
    if len(parts) < 2:
        flash('Неверное имя файла', 'danger')
        return redirect(url_for('task_update', task_id=task_id))
    
    ext = parts[1].lower()
    
    # Создаём папку uploads если нет
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    
    # Определяем тип документа
    doc_type = DocumentType.query.filter(DocumentType.AllowedExtensions.contains(ext)).first()
    
    doc = Document(
        ProjectID=task.ProjectID,
        TaskID=task_id,
        DocTypeID=doc_type.DocTypeID if doc_type else 6,
        DocumentName=f'Отчёт по задаче: {task.TaskName}',
        FileName=filename,
        FilePath=filepath,
        FileSize=os.path.getsize(filepath),
        UploadedBy=current_user.UserID
    )
    db.session.add(doc)
    db.session.commit()
    
    flash('Файл загружен успешно', 'success')
    return redirect(url_for('task_update', task_id=task_id))

@app.route('/time-entries', methods=['GET', 'POST'])
@login_required
def time_entries():
    if request.method == 'POST':
        entry = TimeEntry(
            UserID=current_user.UserID,
            TaskID=request.form.get('task_id'),
            WorkDate=datetime.strptime(request.form.get('work_date'), '%Y-%m-%d'),
            HoursWorked=request.form.get('hours'),
            Description=request.form.get('description'),
            IsBillable=request.form.get('is_billable') == 'on'
        )
        db.session.add(entry)
        db.session.commit()
        flash('Время учтено', 'success')
        return redirect(url_for('time_entries'))
    
    tasks = Task.query.filter_by(AssignedTo=current_user.UserID).filter(Task.StatusID.in_([2, 3, 4])).all()
    entries = TimeEntry.query.filter_by(UserID=current_user.UserID).order_by(TimeEntry.WorkDate.desc()).limit(30).all()
    return render_template('employee/time_entries.html', tasks=tasks, entries=entries, date=date)

# ========== ОТЧЁТЫ ==========

@app.route('/reports')
@login_required
def reports():
    return render_template('reports/index.html')

@app.route('/reports/projects')
@login_required
def report_projects():
    query = Project.query
    if current_user.is_manager():
        query = query.filter_by(ManagerID=current_user.UserID)
    
    projects = query.all()
    
    # Создаём DataFrame для экспорта
    data = []
    for p in projects:
        data.append({
            'Код': p.ProjectCode,
            'Название': p.ProjectName,
            'Тип': p.type.TypeName,
            'Заказчик': p.customer.CustomerName,
            'Статус': p.status.StatusName,
            'Прогресс %': float(p.ProgressPercent),
            'Начало': p.StartDate,
            'Плановое окончание': p.PlannedEndDate,
            'Фактическое окончание': p.ActualEndDate,
            'Бюджет': float(p.Budget) if p.Budget else 0
        })
    
    df = pd.DataFrame(data)
    
    # Экспорт в Excel
    if request.args.get('export') == 'excel':
        # Создаём папку если нет
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        filename = f'projects_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        filepath = os.path.join(upload_folder, filename)
        df.to_excel(filepath, index=False, engine='openpyxl')
        return send_file(filepath, as_attachment=True, download_name=filename)
    
    return render_template('reports/projects.html', projects=projects)

@app.route('/reports/labor')
@login_required
def report_labor():
    start_date = request.args.get('start', datetime.now().replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.args.get('end', datetime.now().strftime('%Y-%m-%d'))
    
    entries = TimeEntry.query.filter(TimeEntry.WorkDate.between(start_date, end_date)).all()
    
    labor_data = {}
    for e in entries:
        key = e.UserID
        if key not in labor_data:
            labor_data[key] = {
                'employee': e.user.FullName,
                'total_hours': 0,
                'billable_hours': 0,
                'entries_count': 0
            }
        labor_data[key]['total_hours'] += float(e.HoursWorked)
        if e.IsBillable:
            labor_data[key]['billable_hours'] += float(e.HoursWorked)
        labor_data[key]['entries_count'] += 1
    
    return render_template('reports/labor.html', labor_data=labor_data, start_date=start_date, end_date=end_date)

@app.route('/reports/efficiency')
@login_required
def report_efficiency():
    employees = User.query.filter_by(RoleID=3).all()
    
    efficiency_data = []
    for emp in employees:
        tasks = Task.query.filter_by(AssignedTo=emp.UserID).all()
        total_tasks = len(tasks)
        completed = len([t for t in tasks if t.StatusID == 5])
        on_time = len([t for t in tasks if t.StatusID == 5 and t.CompletedAt and t.DueDate and t.CompletedAt.date() <= t.DueDate])
        
        planned = sum([float(t.PlannedHours or 0) for t in tasks])
        actual = sum([float(t.ActualHours or 0) for t in tasks])
        
        efficiency_data.append({
            'employee': emp,
            'total_tasks': total_tasks,
            'completed': completed,
            'completion_rate': (completed / total_tasks * 100) if total_tasks > 0 else 0,
            'on_time_rate': (on_time / completed * 100) if completed > 0 else 0,
            'time_accuracy': (planned / actual * 100) if actual > 0 else 0
        })
    
    return render_template('reports/efficiency.html', efficiency_data=efficiency_data)

# ========== ЗАПУСК ==========

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Создание тестового админа
        admin_role = UserRole.query.filter_by(RoleCode='admin').first()
        if admin_role:
            old = User.query.filter_by(Username='admin').first()
            if old:
                db.session.delete(old)
                db.session.commit()
            
            admin = User(
                Username='admin',
                Email='admin@company.com',
                FullName='Администратор',
                RoleID=admin_role.RoleID,
                IsActive=True,
                Salt='salt'
            )
            admin.PasswordHash = generate_password_hash('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Создан админ: admin / admin123")
    
    print("=" * 60)
    print("СЕРВЕР ЗАПУЩЕН: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)