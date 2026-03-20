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
    # Ordena pelo horário de atualização (mais recente no topo)
    pedidos_ordenados = sorted(pedidos, key=lambda x: x.get('ultima_atualizacao', ''), reverse=True)
    return render_template('index.html', pedidos=pedidos_ordenados)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        # Pega o JSON enviado pelo Tiny
        payload = request.get_json(silent=True) or request.form.to_dict()
        
        if not payload:
            return jsonify({"status": "vazio"}), 200

        # O Tiny envia as informações dentro da chave 'dados'
        # Se não houver a chave 'dados', usamos o payload principal como backup
        info = payload.get('dados', payload)

        # Agora buscamos os campos dentro da variável 'info'
        numero = str(info.get('numero', ''))
        status_bruto = str(info.get('descricaoSituacao') or info.get('codigoSituacao') or '').lower()
        
        # Busca o nome do cliente
        cliente_obj = info.get('cliente', {})
        nome_cliente = cliente_obj.get('nome', 'Cliente não identificado') if isinstance(cliente_obj, dict) else str(cliente_obj)

        if not numero:
            print(f"!!! Falha ao localizar número no payload: {payload}")
            return jsonify({"status": "error", "msg": "numero nao encontrado"}), 200

        pedidos = carregar_pedidos()

        # LISTA DE REMOÇÃO: Se o status for um destes, o pedido SAI da tela
        remover = ['cancelado', 'faturado', 'despachado', 'entregue', 'atendido']

        if any(s in status_bruto for s in remover):
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            print(f"--- Pedido {numero} REMOVIDO (Status: {status_bruto})")
        else:
            # Se for status operacional, ADICIONA ou ATUALIZA
            agora = datetime.now().strftime('%H:%M')
            encontrado = False
            
            for p in pedidos:
                if str(p.get('numero')) == numero:
                    p['situacao'] = status_bruto.upper()
                    p['cliente_exibicao'] = nome_cliente
                    p['ultima_atualizacao'] = agora
                    encontrado = True
                    break
            
            if not encontrado:
                novo_pedido = {
                    "numero": numero,
                    "cliente_exibicao": nome_cliente,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora
                }
                pedidos.append(novo_pedido)
                print(f"+++ Pedido {numero} ADICIONADO (Status: {status_bruto})")

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
