# seed.py
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    # Cria a fundação da hierarquia
    admin = User(username='admin', role='Admin')
    admin.set_password('admin123')
    
    # Cria o Operador para testes rápidos
    operador = User(username='operador', role='Operador')
    operador.set_password('bamrj123')

    db.session.add_all([admin, operador])
    db.session.commit()
    print("[SUCESSO] Base do Sistema (Admin e Operador) iniciada!")