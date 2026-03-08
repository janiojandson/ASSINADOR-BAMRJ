from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False) # NOVO CAMPO NOME
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(64), nullable=False)
    
    # ⬅️ NOVO: Trava de segurança para obrigar a troca de senha no primeiro acesso
    must_change_password = db.Column(db.Boolean, default=True) 

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    protocol = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    cpf_cnpj = db.Column(db.String(20), nullable=True)
    solemp = db.Column(db.String(50), nullable=True) # ⬅️ CAMPO SOLEMP
    status = db.Column(db.String(64), default='Caixa de Entrada - Enc. Finanças')
    is_priority = db.Column(db.Boolean, default=False)
    current_observation = db.Column(db.Text, nullable=True)
    uploader_name = db.Column(db.String(64)) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    files = db.relationship('DocumentFile', backref='document', lazy=True, cascade="all, delete-orphan")
    events = db.relationship('Event', backref='document', lazy=True, cascade="all, delete-orphan")

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    user_name = db.Column(db.String(64))
    action = db.Column(db.String(64), nullable=False)
    observation = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class DocumentFile(db.Model):
    __tablename__ = 'document_files'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    file_type = db.Column(db.String(64), nullable=False)