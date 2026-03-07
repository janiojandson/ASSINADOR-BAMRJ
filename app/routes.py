import os, uuid, re
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, session, render_template, current_app, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from sqlalchemy import extract
from app import db
from app.models import User, Document, Event, DocumentFile

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('main.login'))
    
    role = session.get('role'); username = session.get('username')
    is_sub = session.get('is_substitute', False)
    search_query = request.args.get('q', '')
    search_query_clean = re.sub(r'\D', '', search_query) if search_query else ''
    ano_filtro = request.args.get('ano', str(datetime.now().year))

    if role == 'Admin':
        return render_template('dashboard.html', users=User.query.all(), role=role)

    if search_query:
        base_query = Document.query.filter(extract('year', Document.created_at) == int(ano_filtro))
        if role == 'Usuário Comum':
            documents = base_query.filter((Document.cpf_cnpj.ilike(f'%{search_query_clean}%')) & (Document.status == 'Arquivado')).all()
        else:
            documents = base_query.filter((Document.name.ilike(f'%{search_query}%')) | (Document.protocol.ilike(f'%{search_query}%')) | (Document.cpf_cnpj.ilike(f'%{search_query_clean}%'))).all()
        return render_template('dashboard.html', documents=documents, role=role, is_substitute=is_sub)

    inbox_statuses = []
    if role == 'Operador':
        documents = Document.query.filter(Document.status.notin_(['Arquivado', 'Cancelado'])).order_by(Document.is_priority.desc(), Document.created_at.desc()).all()
        date_str = datetime.now().strftime('%Y%m%d')
        # LÓGICA DE AVISO: Operador só é avisado de Devolvidos ou Aguardando Empenho
        inbox_count = sum(1 for d in documents if d.status in ['Devolvido - Operador', 'Aguardando Empenho - Operador'])
        return render_template('dashboard.html', documents=documents, role=role, pre_protocol=f"BAMRJ-{date_str}-{str(uuid.uuid4())[:4].upper()}", inbox_count=inbox_count)
        
    elif role == 'Usuário Comum':
        return render_template('dashboard.html', documents=[], role=role)
        
    elif role in ['Enc_Financas', 'Ajudante_Encarregado']:
        inbox_statuses = ['Caixa de Entrada - Enc. Finanças']
    elif role == 'Chefe_Departamento':
        inbox_statuses = ['Caixa de Entrada - Chefe']
        if is_sub: inbox_statuses.append('Caixa de Entrada - Vice-Diretor')
    elif role == 'Vice_Diretor':
        inbox_statuses = ['Caixa de Entrada - Vice-Diretor']
        if is_sub: inbox_statuses.append('Caixa de Entrada - Diretor')
    elif role == 'Diretor':
        inbox_statuses = ['Caixa de Entrada - Diretor']

    documents = Document.query.filter(Document.status.in_(inbox_statuses)).order_by(Document.is_priority.desc()).all()
    return render_template('dashboard.html', documents=documents, role=role, is_substitute=is_sub, inbox_count=len(documents))

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            session.update({'user_id': user.id, 'username': user.username, 'name': user.name, 'role': user.role})
            return redirect(url_for('main.index'))
    return render_template('login.html')

@main.route('/logout')
def logout(): session.clear(); return redirect(url_for('main.login'))

@main.route('/admin/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'Admin': return "Acesso Negado", 403
    name = request.form.get('name'); username = request.form.get('username'); password = request.form.get('password'); role = request.form.get('role')
    if User.query.filter_by(username=username).first(): return "Erro: Usuário já existe.", 400
    new_user = User(name=name, username=username, role=role)
    new_user.set_password(password)
    db.session.add(new_user); db.session.commit()
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
    if user and user.username != 'admin': db.session.delete(user); db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/toggle_substitute')
def toggle_substitute():
    session['is_substitute'] = not session.get('is_substitute', False); return redirect(url_for('main.index'))

@main.route('/upload', methods=['POST'])
def upload_document():
    if session.get('role') != 'Operador': return "Acesso Negado", 403
    ano_atual = str(datetime.now().year); nome_seguro = secure_filename(request.form.get('process_name'))
    caminho_processo = os.path.join(current_app.config['UPLOAD_FOLDER'], ano_atual, nome_seguro)
    os.makedirs(caminho_processo, exist_ok=True)
    cpf_cnpj_raw = request.form.get('cpf_cnpj', '')
    cpf_cnpj_clean = re.sub(r'\D', '', cpf_cnpj_raw)

    novo_doc = Document(
        protocol=request.form.get('protocol'), name=request.form.get('process_name'),
        cpf_cnpj=cpf_cnpj_clean, is_priority=True if request.form.get('priority') else False,
        current_observation=f"[Início] {request.form.get('observation')}",
        uploader_name=session.get('username'), status='Caixa de Entrada - Enc. Finanças'
    )
    db.session.add(novo_doc); db.session.commit()

    for f in request.files.getlist('minutas'):
        if f and f.filename:
            fname = secure_filename(f.filename); f.save(os.path.join(caminho_processo, fname))
            db.session.add(DocumentFile(document_id=novo_doc.id, filename=os.path.join(ano_atual, nome_seguro, fname).replace('\\', '/'), file_type='Minuta'))
    for f in request.files.getlist('anexos'):
        if f and f.filename:
            fname = secure_filename(f.filename); f.save(os.path.join(caminho_processo, fname))
            db.session.add(DocumentFile(document_id=novo_doc.id, filename=os.path.join(ano_atual, nome_seguro, fname).replace('\\', '/'), file_type='Anexo'))
    db.session.commit(); return redirect(url_for('main.index'))

# --- ROTAS DE EDIÇÃO PARA OPERADOR ---
@main.route('/edit/<int:doc_id>')
def edit_process(doc_id):
    if session.get('role') != 'Operador': return "Acesso Negado", 403
    doc = Document.query.get_or_404(doc_id)
    if doc.status != 'Devolvido - Operador': return "Processo não está em status de devolução", 403
    return render_template('edit_process.html', doc=doc)

@main.route('/update_process/<int:doc_id>', methods=['POST'])
def update_process(doc_id):
    if session.get('role') != 'Operador': return "Acesso Negado", 403
    doc = Document.query.get_or_404(doc_id)
    
    doc.name = request.form.get('process_name')
    doc.cpf_cnpj = re.sub(r'\D', '', request.form.get('cpf_cnpj', ''))
    doc.is_priority = True if request.form.get('priority') else False
    
    ano_atual = str(doc.created_at.year)
    nome_seguro = secure_filename(doc.name)
    caminho_processo = os.path.join(current_app.config['UPLOAD_FOLDER'], ano_atual, nome_seguro)
    os.makedirs(caminho_processo, exist_ok=True)
    
    for f in request.files.getlist('minutas'):
        if f and f.filename:
            fname = secure_filename(f.filename); f.save(os.path.join(caminho_processo, fname))
            db.session.add(DocumentFile(document_id=doc.id, filename=os.path.join(ano_atual, nome_seguro, fname).replace('\\', '/'), file_type='Minuta'))
    for f in request.files.getlist('anexos'):
        if f and f.filename:
            fname = secure_filename(f.filename); f.save(os.path.join(caminho_processo, fname))
            db.session.add(DocumentFile(document_id=doc.id, filename=os.path.join(ano_atual, nome_seguro, fname).replace('\\', '/'), file_type='Anexo'))
            
    obs = request.form.get('observation')
    doc.status = 'Caixa de Entrada - Enc. Finanças'
    db.session.add(Event(document_id=doc.id, user_name=session.get('username'), action='RETRAMITAR', observation=obs))
    doc.current_observation += f"\n[{datetime.now().strftime('%d/%m %H:%M')} - Operador]: [Revisado/Retramitado] {obs}"
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if session.get('role') != 'Operador': return "Acesso Negado", 403
    f = DocumentFile.query.get_or_404(file_id)
    doc_id = f.document_id
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for('main.edit_process', doc_id=doc_id))
# -------------------------------------------

@main.route('/process_action/<int:doc_id>/<action>', methods=['POST'])
def process_action(doc_id, action):
    doc = Document.query.get_or_404(doc_id)
    obs = request.form.get('new_observation'); username = session.get('username')
    role = session.get('role'); is_sub = session.get('is_substitute', False)
    
    db.session.add(Event(document_id=doc.id, user_name=username, action=action.upper(), observation=obs))
    if obs:
        cargo = f"{role} (SUBSTITUTO)" if is_sub else ('Enc. Finanças' if role == 'Enc_Financas' else role)
        doc.current_observation += f"\n[{datetime.now().strftime('%d/%m %H:%M')} - {cargo}]: {obs}"
        
    if action == 'rejeitar': 
        doc.status = 'Devolvido - Operador'
    elif action == 'aprovar':
        if doc.status == 'Caixa de Entrada - Enc. Finanças': doc.status = 'Caixa de Entrada - Chefe'
        elif doc.status == 'Caixa de Entrada - Chefe':
            if is_sub and role == 'Chefe_Departamento': doc.status = 'Caixa de Entrada - Diretor'
            else: doc.status = 'Caixa de Entrada - Vice-Diretor'
        elif doc.status == 'Caixa de Entrada - Vice-Diretor':
            if is_sub and role == 'Vice_Diretor': doc.status = 'Aguardando Empenho - Operador'
            else: doc.status = 'Caixa de Entrada - Diretor'
        elif doc.status == 'Caixa de Entrada - Diretor': doc.status = 'Aguardando Empenho - Operador'
            
    db.session.commit(); return redirect(url_for('main.index'))

@main.route('/cancel_document/<int:doc_id>', methods=['POST'])
def cancel_document(doc_id):
    if session.get('role') != 'Operador': return "Acesso Negado", 403
    doc = Document.query.get_or_404(doc_id)
    doc.status = 'Cancelado'; obs = 'Processo cancelado pelo operador.'
    db.session.add(Event(document_id=doc.id, user_name=session.get('username'), action='CANCELAR', observation=obs))
    doc.current_observation += f"\n[{datetime.now().strftime('%d/%m %H:%M')} - Operador]: {obs}"
    db.session.commit(); return redirect(url_for('main.index'))

@main.route('/upload_ne/<int:doc_id>', methods=['POST'])
def upload_ne(doc_id):
    if session.get('role') != 'Operador': return "Acesso Negado", 403
    doc = Document.query.get_or_404(doc_id); arquivo_ne = request.files.get('nota_empenho')
    if arquivo_ne and arquivo_ne.filename:
        ano_atual = str(datetime.now().year); nome_seguro = secure_filename(doc.name)
        caminho_processo = os.path.join(current_app.config['UPLOAD_FOLDER'], ano_atual, nome_seguro)
        os.makedirs(caminho_processo, exist_ok=True)
        fname = secure_filename(arquivo_ne.filename); arquivo_ne.save(os.path.join(caminho_processo, fname))
        db.session.add(DocumentFile(document_id=doc.id, filename=os.path.join(ano_atual, nome_seguro, fname).replace('\\', '/'), file_type='Nota de Empenho'))
        doc.status = 'Arquivado'
        db.session.add(Event(document_id=doc.id, user_name=session.get('username'), action='ANEXAR_NE', observation='Nota de Empenho anexada.'))
        db.session.commit()
    return redirect(url_for('main.index'))

@main.route('/view/<int:doc_id>')
def view_process(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template('viewer.html', doc=doc, role=session.get('role'))

@main.route('/arquivo')
def arquivo():
    if 'user_id' not in session: return redirect(url_for('main.login'))
    role = session.get('role')
    search_query = request.args.get('q', '')
    search_query_clean = re.sub(r'\D', '', search_query) if search_query else ''
    ano_filtro = request.args.get('ano', str(datetime.now().year))
    query = Document.query.filter(Document.status.in_(['Arquivado', 'Cancelado'])).filter(extract('year', Document.created_at) == int(ano_filtro))
    if search_query:
        query = query.filter((Document.name.ilike(f'%{search_query}%')) | (Document.protocol.ilike(f'%{search_query}%')) | (Document.cpf_cnpj.ilike(f'%{search_query_clean}%')))
    documents = query.order_by(Document.created_at.desc()).all()
    return render_template('arquivo.html', documents=documents, role=role)

@main.route('/get_pdf/<path:filename>')
def get_pdf(filename): return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main.route('/api/check_inbox')
def check_inbox():
    if 'user_id' not in session: return jsonify({'count': 0})
    role = session.get('role'); is_sub = session.get('is_substitute', False); inbox_statuses = []
    
    if role in ['Enc_Financas', 'Ajudante_Encarregado']: inbox_statuses = ['Caixa de Entrada - Enc. Finanças']
    elif role == 'Chefe_Departamento':
        inbox_statuses = ['Caixa de Entrada - Chefe']
        if is_sub: inbox_statuses.append('Caixa de Entrada - Vice-Diretor')
    elif role == 'Vice_Diretor':
        inbox_statuses = ['Caixa de Entrada - Vice-Diretor']
        if is_sub: inbox_statuses.append('Caixa de Entrada - Diretor')
    elif role == 'Diretor': inbox_statuses = ['Caixa de Entrada - Diretor']
    elif role == 'Operador':
        # POLING: API SÓ AVISA SE CHEGAR DEVOLVIDO OU EMPENHO
        count = Document.query.filter(Document.status.in_(['Devolvido - Operador', 'Aguardando Empenho - Operador'])).count()
        return jsonify({'count': count})
    else: return jsonify({'count': 0}) 
        
    count = Document.query.filter(Document.status.in_(inbox_statuses)).count()
    return jsonify({'count': count})