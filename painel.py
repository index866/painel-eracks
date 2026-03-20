import json
import os
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

app = Flask(__name__) # ESTA LINHA PRECISA VIR ANTES DE TUDO

ARQUIVO_JSON = 'pedidos_eracks.json'

def carregar_pedidos():
    if not os.path.exists(ARQUIVO_JSON):
        return []
    with open(ARQUIVO_JSON, 'r') as f:
        return json.load(f)

def salvar_pedidos(pedidos):
    with open(ARQUIVO_JSON, 'w') as f:
        json.dump(pedidos, f, indent=4)

@app.route('/')
def index():
    pedidos = carregar_pedidos()
    return render_template('index.html', pedidos=pedidos)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload:
            return jsonify({"status": "vazio"}), 200

        # Pega os dados dentro da chave 'dados' enviada pelo Tiny
        info = payload.get('dados', payload)
        numero = str(info.get('numero', ''))
        status_bruto = str(info.get('descricaoSituacao') or info.get('codigoSituacao') or '').lower()
        
        cliente_obj = info.get('cliente', {})
        nome_cliente = cliente_obj.get('nome', 'Cliente não identificado') if isinstance(cliente_obj, dict) else str(cliente_obj)

        if not numero:
            print(f"!!! Pedido ignorado: não achei o campo 'numero'. Dados: {payload}")
            return jsonify({"status": "error", "msg": "numero nao encontrado"}), 200

        pedidos = carregar_pedidos()
        # Status que fazem o pedido SAIR da tela
        remover = ['cancelado', 'faturado', 'despachado', 'entregue', 'atendido']

        if any(s in status_bruto for s in remover):
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            print(f"--- Pedido {numero} REMOVIDO (Status: {status_bruto})")
        else:
            # Ajuste de Fuso Horário (Brasil UTC -3)
            fuso_brasil = datetime.now() - timedelta(hours=3)
            agora = fuso_brasil.strftime('%H:%M')
            
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
        print(f"ERRO NO WEBHOOK: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
