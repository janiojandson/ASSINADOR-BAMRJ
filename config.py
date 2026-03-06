# config.py
import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

class Config:
    # Segurança
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-padrao-de-seguranca'
    
    # Banco de Dados
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuração de Uploads (O arquivo fica, o evento anda)
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limite de 16MB para PDFs