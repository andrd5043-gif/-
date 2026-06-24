import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = 'mssql+pyodbc://@DESKTOP-MIUGTE0\\SQLEXPRESS/ProjectManagement?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    
    ALLOWED_EXTENSIONS = {
        'drawing': ['dwg', 'dxf', 'pdf'],
        'estimate': ['xls', 'xlsx', 'pdf'],
        'report': ['doc', 'docx', 'pdf'],
        'contract': ['pdf', 'doc', 'docx'],
        'act': ['pdf'],
        'other': ['pdf', 'doc', 'docx', 'jpg', 'png']
    }