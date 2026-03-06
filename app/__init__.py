# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

# Instância global do Banco de Dados
db = SQLAlchemy()

def create_app(config_class=Config):
    # Inicialização do App (Factory)
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializa os plugins (SQLAlchemy)
    db.init_app(app)

    # Importa e registra o Blueprint de rotas (modularidade)
    # A importação ocorre dentro da função para evitar referência circular
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app