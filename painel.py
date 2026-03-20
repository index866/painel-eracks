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
    # Ordena: os que atualizaram por último aparecem primeiro
    pedidos_ordenados = sorted(pedidos, key=lambda x: x.get('ultima_atualizacao', ''), reverse=True)
    return render_template('index.html', pedidos=pedidos_ordenados)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        dados = request.get_json(silent=True)
        if not dados:
            return jsonify({"status": "error", "msg": "JSON vazio"}), 200

        # Extração flexível de dados (aceita várias versões do Tiny)
        numero = str(dados.get('numero') or dados.get('numero_pedido') or '')
        status_bruto = str(dados.get('situacao') or dados.get('status') or '').lower()
        
        # Extração do nome do cliente (Tenta objeto ou string direta)
        cliente_data = dados.get('cliente', {})
        if isinstance(cliente_data, dict):
            nome_cliente = cliente_data.get('nome', 'Cliente s/ Nome')
        else:
            nome_cliente = str(cliente_data)

        if not numero:
            return jsonify({"status": "error", "msg": "Pedido sem numero"}), 200

        pedidos = carregar_pedidos()

        # LISTA DE STATUS QUE FAZEM O PEDIDO SUMIR DA TELA
        status_remover = ['cancelado', 'faturado', 'atendido', 'concluido', 'despachado', 'entregue']

        if any(s in status_bruto for s in status_remover):
            # Remove o pedido da lista se ele for faturado ou cancelado
            pedidos = [p for p in pedidos if str(p.get('numero') or p.get('numero_pedido')) != numero]
            print(f">>> [REMOVIDO] Pedido {numero} saiu da tela (Status: {status_bruto})")
        else:
            # Atualiza ou Adiciona se for um status ativo (Aberto, Preparando, etc)
            agora = datetime.now().strftime('%H:%M')
            encontrado = False
            for p in pedidos:
                if str(p.get('numero') or p.get('numero_pedido')) == numero:
                    p.update(dados)
                    p['cliente_exibicao'] = nome_cliente # Padroniza o nome
                    p['ultima_atualizacao'] = agora
                    encontrado = True
                    break
            
            if not encontrado:
                dados['cliente_exibicao'] = nome_cliente
                dados['ultima_atualizacao'] = agora
                pedidos.append(dados)
            print(f">>> [ATIVO] Pedido {numero} atualizado (Status: {status_bruto})")

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"ERRO WEBHOOK: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
