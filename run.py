# run.py
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Roda o servidor na porta 5000, com debug ativado para desenvolvimento
    app.run(debug=True, port=5000)