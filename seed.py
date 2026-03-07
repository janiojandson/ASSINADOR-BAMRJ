# seed.py
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    
    # Criando os usuários iniciais já com o campo 'name'
    admin = User(name='Administrador do Sistema', username='admin', role='Admin')
    admin.set_password('admin123')
    
    operador = User(name='Operador BAMRJ', username='operador', role='Operador')
    operador.set_password('bamrj123')

    db.session.add_all([admin, operador])
    db.session.commit()
    print("[SUCESSO] Base do Sistema iniciada com sucesso!")