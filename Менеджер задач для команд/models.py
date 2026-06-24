from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class UserRole(db.Model):
    __tablename__ = 'UserRoles'
    RoleID = db.Column(db.Integer, primary_key=True)
    RoleName = db.Column(db.String(50))
    RoleCode = db.Column(db.String(20))
    Permissions = db.Column(db.Text)

class User(UserMixin, db.Model):
    __tablename__ = 'Users'
    UserID = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(50), unique=True)
    Email = db.Column(db.String(100))
    PasswordHash = db.Column(db.String(255))
    Salt = db.Column(db.String(100))
    FullName = db.Column(db.String(100))
    Phone = db.Column(db.String(20))
    Department = db.Column(db.String(100))
    Position = db.Column(db.String(100))
    RoleID = db.Column(db.Integer, db.ForeignKey('UserRoles.RoleID'))
    IsActive = db.Column(db.Boolean, default=True)
    LastLoginAt = db.Column(db.DateTime)
    
    role = db.relationship('UserRole', backref='users')
    
    def get_id(self):
        return str(self.UserID)
    
    def check_password(self, password):
        return check_password_hash(self.PasswordHash, password)
    
    def is_admin(self):
        return self.role and self.role.RoleCode == 'admin'
    
    def is_manager(self):
        return self.role and self.role.RoleCode == 'manager'
    
    def is_employee(self):
        return self.role and self.role.RoleCode == 'employee'

class ProjectType(db.Model):
    __tablename__ = 'ProjectTypes'
    TypeID = db.Column(db.Integer, primary_key=True)
    TypeName = db.Column(db.String(100))
    TypeCode = db.Column(db.String(20))
    Description = db.Column(db.String(500))

class ProjectStatus(db.Model):
    __tablename__ = 'ProjectStatuses'
    StatusID = db.Column(db.Integer, primary_key=True)
    StatusName = db.Column(db.String(50))
    StatusCode = db.Column(db.String(20))
    ColorCode = db.Column(db.String(7))

class TaskStatus(db.Model):
    __tablename__ = 'TaskStatuses'
    TaskStatusID = db.Column(db.Integer, primary_key=True)
    StatusName = db.Column(db.String(50))
    StatusCode = db.Column(db.String(20))
    ColorCode = db.Column(db.String(7))

class Customer(db.Model):
    __tablename__ = 'Customers'
    CustomerID = db.Column(db.Integer, primary_key=True)
    CustomerName = db.Column(db.String(200))
    CustomerType = db.Column(db.String(20))
    INN = db.Column(db.String(12))
    ContactPerson = db.Column(db.String(100))
    ContactPhone = db.Column(db.String(20))
    ContactEmail = db.Column(db.String(100))
    IsActive = db.Column(db.Boolean, default=True)

class Project(db.Model):
    __tablename__ = 'Projects'
    ProjectID = db.Column(db.Integer, primary_key=True)
    ProjectCode = db.Column(db.String(20), unique=True)
    ProjectName = db.Column(db.String(200))
    TypeID = db.Column(db.Integer, db.ForeignKey('ProjectTypes.TypeID'))
    CustomerID = db.Column(db.Integer, db.ForeignKey('Customers.CustomerID'))
    StatusID = db.Column(db.Integer, db.ForeignKey('ProjectStatuses.StatusID'))
    ManagerID = db.Column(db.Integer, db.ForeignKey('Users.UserID'))
    Description = db.Column(db.Text)
    StartDate = db.Column(db.Date)
    PlannedEndDate = db.Column(db.Date)
    ActualEndDate = db.Column(db.Date)
    Budget = db.Column(db.Numeric(18, 2))
    Priority = db.Column(db.Integer, default=3)
    ProgressPercent = db.Column(db.Numeric(5, 2), default=0)
    IsArchived = db.Column(db.Boolean, default=False)
    CreatedAt = db.Column(db.DateTime, default=datetime.utcnow)
    
    type = db.relationship('ProjectType')
    status = db.relationship('ProjectStatus')
    customer = db.relationship('Customer')
    manager = db.relationship('User')

class ProjectStage(db.Model):
    __tablename__ = 'ProjectStages'
    StageID = db.Column(db.Integer, primary_key=True)
    ProjectID = db.Column(db.Integer, db.ForeignKey('Projects.ProjectID'))
    StageName = db.Column(db.String(100))
    StageNumber = db.Column(db.Integer)
    PlannedStartDate = db.Column(db.Date)
    PlannedEndDate = db.Column(db.Date)
    ActualStartDate = db.Column(db.Date)
    ActualEndDate = db.Column(db.Date)
    StatusID = db.Column(db.Integer, db.ForeignKey('ProjectStatuses.StatusID'))
    WeightPercent = db.Column(db.Numeric(5, 2))
    IsCritical = db.Column(db.Boolean, default=False)

class Task(db.Model):
    __tablename__ = 'Tasks'
    TaskID = db.Column(db.Integer, primary_key=True)
    ProjectID = db.Column(db.Integer, db.ForeignKey('Projects.ProjectID'))
    StageID = db.Column(db.Integer, db.ForeignKey('ProjectStages.StageID'))
    TaskName = db.Column(db.String(200))
    Description = db.Column(db.Text)
    AssignedTo = db.Column(db.Integer, db.ForeignKey('Users.UserID'))
    CreatedBy = db.Column(db.Integer, db.ForeignKey('Users.UserID'))
    StatusID = db.Column(db.Integer, db.ForeignKey('TaskStatuses.TaskStatusID'))
    Priority = db.Column(db.Integer, default=3)
    PlannedHours = db.Column(db.Numeric(6, 2))
    ActualHours = db.Column(db.Numeric(6, 2))
    DueDate = db.Column(db.Date)
    CompletedAt = db.Column(db.DateTime)
    
    project = db.relationship('Project')
    status = db.relationship('TaskStatus')
    assignee = db.relationship('User', foreign_keys=[AssignedTo])

class TimeEntry(db.Model):
    __tablename__ = 'TimeEntries'
    EntryID = db.Column(db.Integer, primary_key=True)
    UserID = db.Column(db.Integer, db.ForeignKey('Users.UserID'))
    TaskID = db.Column(db.Integer, db.ForeignKey('Tasks.TaskID'))
    WorkDate = db.Column(db.Date)
    HoursWorked = db.Column(db.Numeric(4, 2))
    Description = db.Column(db.String(500))
    IsBillable = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref='time_entries', lazy=True)
    task = db.relationship('Task', backref='time_entries', lazy=True)
    user = db.relationship('User', foreign_keys=[UserID])
    task = db.relationship('Task', foreign_keys=[TaskID])
class DocumentType(db.Model):
    __tablename__ = 'DocumentTypes'
    DocTypeID = db.Column(db.Integer, primary_key=True)
    TypeName = db.Column(db.String(50))
    AllowedExtensions = db.Column(db.String(200))

class Document(db.Model):
    __tablename__ = 'Documents'
    DocumentID = db.Column(db.Integer, primary_key=True)
    ProjectID = db.Column(db.Integer, db.ForeignKey('Projects.ProjectID'))
    TaskID = db.Column(db.Integer, db.ForeignKey('Tasks.TaskID'))
    DocTypeID = db.Column(db.Integer, db.ForeignKey('DocumentTypes.DocTypeID'))
    DocumentName = db.Column(db.String(200))
    FileName = db.Column(db.String(255))
    FilePath = db.Column(db.String(500))
    FileSize = db.Column(db.BigInteger)
    UploadedBy = db.Column(db.Integer, db.ForeignKey('Users.UserID'))
    CreatedAt = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.relationship('DocumentType', backref='documents', lazy=True)
    uploader = db.relationship('User', backref='uploaded_documents', lazy=True)
    project = db.relationship('Project', backref='documents', lazy=True)
    task = db.relationship('Task', backref='documents', lazy=True)
class WorkAct(db.Model):
    __tablename__ = 'WorkActs'
    ActID = db.Column(db.Integer, primary_key=True)
    ActNumber = db.Column(db.String(20), unique=True)
    ProjectID = db.Column(db.Integer, db.ForeignKey('Projects.ProjectID'))
    ActDate = db.Column(db.Date)
    PeriodStart = db.Column(db.Date)
    PeriodEnd = db.Column(db.Date)
    TotalHours = db.Column(db.Numeric(8, 2))
    TotalAmount = db.Column(db.Numeric(18, 2))
    Status = db.Column(db.String(20), default='draft')
    SignedByCustomer = db.Column(db.Boolean, default=False)
    CreatedBy = db.Column('CreatedBy', db.Integer, db.ForeignKey('Users.UserID'))  # Явное указание имени колонки
    
    project = db.relationship('Project')
    creator = db.relationship('User', foreign_keys=[CreatedBy])
    