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
    # Ordenar pelos mais recentes primeiro
    pedidos_ordenados = sorted(pedidos, key=lambda x: x.get('ultima_atualizacao', ''), reverse=True)
    return render_template('index.html', pedidos=pedidos_ordenados)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        # Pega os dados independente de como o Tiny enviar (JSON ou Formulário)
        if request.is_json:
            dados = request.get_json()
        else:
            dados = request.form.to_dict()

        if not dados:
            return jsonify({"status": "vazio"}), 200

        # Extração de campos principais
        numero = str(dados.get('numero') or dados.get('numero_pedido') or '')
        status_bruto = str(dados.get('situacao') or dados.get('status') or '').lower()
        
        # Trata o nome do cliente
        cliente_obj = dados.get('cliente', {})
        nome_cliente = cliente_obj.get('nome') if isinstance(cliente_obj, dict) else str(cliente_obj)
        if not nome_cliente or nome_cliente == '{}':
            nome_cliente = "Cliente não identificado"

        if not numero:
            return jsonify({"status": "sem_numero"}), 200

        pedidos = carregar_pedidos()

        # Filtro de saída (Status que removem do painel)
        remover = ['cancelado', 'faturado', 'atendido', 'concluido', 'despachado', 'entregue']

        if any(s in status_bruto for s in remover):
            # Remove o pedido se ele foi faturado ou cancelado
            pedidos = [p for p in pedidos if str(p.get('numero') or p.get('numero_pedido')) != numero]
        else:
            # Adiciona ou atualiza se for status operacional (Aberto, Preparando, etc)
            agora = datetime.now().strftime('%H:%M')
            encontrado = False
            for p in pedidos:
                if str(p.get('numero') or p.get('numero_pedido')) == numero:
                    p.update(dados)
                    p['cliente_exibicao'] = nome_cliente
                    p['ultima_atualizacao'] = agora
                    encontrado = True
                    break
            
            if not encontrado:
                dados['cliente_exibicao'] = nome_cliente
                dados['ultima_atualizacao'] = agora
                pedidos.append(dados)

        salvar_pedidos(pedidos)
        return jsonify({"status": "sucesso"}), 200

    except Exception as e:
        print(f"Erro no Webhook: {e}")
        return jsonify({"status": "erro", "detalhe": str(e)}), 200

if __name__ == '__main__':
    # Configuração de porta para o Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
