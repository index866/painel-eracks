import json
import os
import unicodedata
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

ARQUIVO_BANCO = 'pedidos_eracks.json'

def remover_acentos(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower().strip()

def carregar_dados():
    if os.path.exists(ARQUIVO_BANCO):
        try:
            with open(ARQUIVO_BANCO, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def salvar_dados(dados):
    with open(ARQUIVO_BANCO, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

pedidos_painel = carregar_dados()

# --- FORMATAÇÃO ORIGINAL RESTAURADA ---
HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Painel Eracks - Operacional</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="10">
    <style>
        body { background-color: #f4f7f6; }
        .navbar { background-color: #2c3e50; border-bottom: 5px solid #e74c3c; }
        .card-pedido { border-radius: 10px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .badge-ecommerce { background-color: #ebedef; color: #555; font-size: 0.75rem; font-weight: bold; }
        .status-badge { padding: 8px 15px; border-radius: 50px; font-weight: bold; text-transform: uppercase; }
        .at-info { font-size: 0.7rem; color: #95a5a6; margin-top: 10px; text-align: right; font-style: italic; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark p-3 mb-4">
        <div class="container d-flex justify-content-between align-items-center">
            <span class="navbar-brand h1 mb-0">📦 PAINEL ERACKS</span>
            <span class="badge bg-light text-dark">Pendentes: {{ pedidos|length }}</span>
        </div>
    </nav>

    <div class="container">
        <div class="row">
            {% for pedido in pedidos %}
            <div class="col-md-4 mb-4">
                <div class="card card-pedido">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <span class="badge badge-ecommerce text-uppercase">{{ pedido.nomeEcommerce }}</span>
                            <small class="text-muted">{{ pedido.data }}</small>
                        </div>
                        <h5 class="text-primary">Pedido #{{ pedido.numero }}</h5>
                        <p class="mb-1 text-truncate"><strong>Cliente:</strong> {{ pedido.cliente }}</p>
                        
                        <div class="mt-3 d-flex flex-column align-items-center">
                            <span class="badge status-badge w-100 
                                {% if 'aprovado' in pedido.situacao|lower %}bg-success
                                {% elif 'preparando' in pedido.situacao|lower %}bg-info text-dark
                                {% else %}bg-warning text-dark{% endif %}">
                                {{ pedido.situacao }}
                            </span>
                            <div class="at-info w-100">🕒 Atualizado às {{ pedido.atualizado_em }}</div>
                        </div>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="col-12 text-center mt-5">
                <div class="p-5 border bg-white rounded shadow-sm">
                    <h4 class="text-muted">Nenhum pedido pendente!</h4>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
@app.route('/webhook-tiny', methods=['POST'])
def gerenciar_pedidos():
    global pedidos_painel
    
    # Status que fazem o pedido SAIR da tela
    termos_encerrados = ["faturado", "cancelado", "atendido", "enviado", "entregue", "concluido"]

    if request.method == 'POST':
        try:
            dados_brutos = request.get_json()
            conteudo = dados_brutos.get('dados', dados_brutos)
            
            id_recebido = str(conteudo.get('id') or conteudo.get('idPedido') or "")
            situacao_vinda = str(conteudo.get('situacao') or conteudo.get('situacao_descricao', 'Pendente'))
            
            if not id_recebido:
                return jsonify({"status": "erro"}), 200

            # Lógica de Remoção: Se o status for finalizador, deleta do JSON
            status_normalizado = remover_acentos(situacao_vinda)
            if any(termo in status_normalizado for termo in termos_encerrados):
                pedidos_painel = [p for p in pedidos_painel if str(p.get('id')) != id_recebido]
                salvar_dados(pedidos_painel)
                return jsonify({"status": "removido"}), 200

            # Lógica de Inserção/Atualização
            ecommerce = conteudo.get('nome_ecommerce') or conteudo.get('nomeEcommerce') or "Venda Direta"
            
            novo_pedido = {
                "id": id_recebido,
                "numero": conteudo.get('numero') or "S/N",
                "situacao": situacao_vinda,
                "cliente": conteudo.get('cliente', {}).get('nome') or "Cliente Geral",
                "data": conteudo.get('data', datetime.now().strftime("%d/%m/%Y")),
                "nomeEcommerce": ecommerce,
                "atualizado_em": datetime.now().strftime("%H:%M")
            }

            for i, p in enumerate(pedidos_painel):
                if str(p.get('id')) == id_recebido:
                    pedidos_painel[i] = novo_pedido
                    break
            else:
                pedidos_painel.insert(0, novo_pedido)

            salvar_dados(pedidos_painel)
            return jsonify({"status": "sucesso"}), 200

        except Exception as e:
            return jsonify({"status": "erro"}), 500

    # Filtro de segurança antes de renderizar a página
    ativos = [p for p in pedidos_painel if not any(t in remover_acentos(p['situacao']) for t in termos_encerrados)]
    return render_template_string(HTML_PAINEL, pedidos=ativos)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
