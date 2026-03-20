from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
DATA_FILE = 'pedidos_eracks.json'

def carregar_pedidos():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_pedidos(pedidos):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(pedidos, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    pedidos = carregar_pedidos()
    # Mantém a contagem de pendentes para o seu painel
    total_pendentes = len(pedidos)
    agora = datetime.now().strftime('%H:%M:%S')
    return render_template('index.html', pedidos=pedidos, total=total_pendentes, hora=agora)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        dados = request.get_json(silent=True)
        if not dados:
            return jsonify({"status": "error"}), 200

        # Identificação e Status
        numero = str(dados.get('numero') or dados.get('numero_pedido') or '')
        status = str(dados.get('situacao') or dados.get('status') or '').lower()

        if not numero:
            return jsonify({"status": "error"}), 200

        pedidos = carregar_pedidos()

        # LISTA DE REMOÇÃO (Se o Tiny mandar um desses, o pedido SAI da tela)
        status_para_sair = ['cancelado', 'faturado', 'atendido', 'concluido', 'despachado']

        if any(s in status for s in status_para_sair):
            pedidos = [p for p in pedidos if str(p.get('numero') or p.get('numero_pedido')) != numero]
        else:
            # ATUALIZA OU ADICIONA (Se for Aberto, Preparando, etc)
            encontrado = False
            for p in pedidos:
                if str(p.get('numero') or p.get('numero_pedido')) == numero:
                    p.update(dados)
                    p['ultima_atualizacao'] = datetime.now().strftime('%H:%M')
                    encontrado = True
                    break
            if not encontrado:
                dados['ultima_atualizacao'] = datetime.now().strftime('%H:%M')
                pedidos.append(dados)

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    # O Render usa a porta 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
