import os, uuid
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, session, render_template, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app import db
from app.models import User, Document, Event, DocumentFile

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    role = session.get('role')
    username = session.get('username')
    is_sub = session.get('is_substitute', False)
    search_query = request.args.get('q', '')

    if role == 'Admin':
        users = User.query.all()
        return render_template('dashboard.html', users=users, role=role)

    inbox_statuses = []
    if role == 'Operador':
        documents = Document.query.filter_by(uploader_name=username).all()
        date_str = datetime.now().strftime('%Y%m%d')
        pre_protocol = f"BAMRJ-{date_str}-{str(uuid.uuid4())[:4].upper()}"
        return render_template('dashboard.html', documents=documents, role=role, pre_protocol=pre_protocol)
        
    elif role in ['Encarregado', 'Ajudante_Encarregado']:
        inbox_statuses = ['Caixa de Entrada - Encarregado']
    elif role == 'Chefe_Departamento':
        inbox_statuses = ['Caixa de Entrada - Chefe']
        if is_sub: inbox_statuses.append('Caixa de Entrada - Vice-Diretor')
    elif role == 'Vice_Diretor':
        inbox_statuses = ['Caixa de Entrada - Vice-Diretor']
        if is_sub: inbox_statuses.append('Caixa de Entrada - Diretor')
    elif role == 'Diretor':
        inbox_statuses = ['Caixa de Entrada - Diretor']

    if search_query:
        documents = Document.query.filter((Document.name.ilike(f'%{search_query}%')) | (Document.protocol.ilike(f'%{search_query}%'))).all()
    else:
        documents = Document.query.filter(Document.status.in_(inbox_statuses)).order_by(Document.is_priority.desc()).all()

    return render_template('dashboard.html', documents=documents, role=role, is_substitute=is_sub, inbox_count=len(documents))

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('main.index'))
    return render_template('login.html')

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@main.route('/admin/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'Admin': return "Acesso Negado", 403
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    
    if User.query.filter_by(username=username).first():
        return "Erro: Usuário já existe.", 400
        
    new_user = User(username=username, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/admin/edit_user', methods=['POST'])
def edit_user():
    if session.get('role') != 'Admin': return "Acesso Negado", 403
    user = User.query.get(request.form.get('user_id'))
    if user:
        user.role = request.form.get('role')
        if request.form.get('password'): user.set_password(request.form.get('password'))
        db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'Admin': return "Acesso Negado", 403
    user = User.query.get(user_id)
    if user and user.username != 'admin':
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('main.index'))

# --- Rotas de Fluxo e Visualização ---
@main.route('/toggle_substitute')
def toggle_substitute():
    session['is_substitute'] = not session.get('is_substitute', False)
    return redirect(url_for('main.index'))

@main.route('/upload', methods=['POST'])
def upload_document():
    if session.get('role') != 'Operador': return "Acesso Negado", 403
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    novo_doc = Document(
        protocol=request.form.get('protocol'), name=request.form.get('process_name'),
        is_priority=True if request.form.get('priority') else False,
        current_observation=f"[Início] {request.form.get('observation')}",
        uploader_name=session.get('username'), status='Caixa de Entrada - Encarregado'
    )
    db.session.add(novo_doc)
    db.session.commit()
    for f in request.files.getlist('minutas'):
        if f and f.filename:
            fname = secure_filename(f.filename); f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
            db.session.add(DocumentFile(document_id=novo_doc.id, filename=fname, file_type='Minuta'))
    for f in request.files.getlist('anexos'):
        if f and f.filename:
            fname = secure_filename(f.filename); f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
            db.session.add(DocumentFile(document_id=novo_doc.id, filename=fname, file_type='Anexo'))
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/process_action/<int:doc_id>/<action>', methods=['POST'])
def process_action(doc_id, action):
    doc = Document.query.get_or_404(doc_id)
    obs = request.form.get('new_observation'); username = session.get('username')
    role = session.get('role'); is_sub = session.get('is_substitute', False)
    db.session.add(Event(document_id=doc.id, user_name=username, action=action.upper(), observation=obs))
    if obs:
        cargo = f"{role} (SUBSTITUTO)" if is_sub else role
        doc.current_observation += f"\n[{datetime.now().strftime('%d/%m %H:%M')} - {cargo}]: {obs}"
    if action == 'rejeitar': doc.status = 'Devolvido - Operador'
    elif action == 'aprovar':
        if doc.status == 'Caixa de Entrada - Encarregado': doc.status = 'Caixa de Entrada - Chefe'
        elif doc.status == 'Caixa de Entrada - Chefe': doc.status = 'Caixa de Entrada - Vice-Diretor'
        elif doc.status == 'Caixa de Entrada - Vice-Diretor': doc.status = 'Caixa de Entrada - Diretor'
        elif doc.status == 'Caixa de Entrada - Diretor' or (is_sub and role == 'Vice_Diretor'): doc.status = 'Finalizado - Autorizado'
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/view/<int:doc_id>')
def view_process(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template('viewer.html', doc=doc)

@main.route('/get_pdf/<filename>')
def get_pdf(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)