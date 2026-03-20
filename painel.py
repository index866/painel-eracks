import json
import os
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

app = Flask(__name__)

ARQUIVO_JSON = 'pedidos_eracks.json'

def carregar_pedidos():
    if not os.path.exists(ARQUIVO_JSON):
        return []
    try:
        with open(ARQUIVO_JSON, 'r') as f:
            return json.load(f)
    except:
        return []

def salvar_pedidos(pedidos):
    with open(ARQUIVO_JSON, 'w') as f:
        json.dump(pedidos, f, indent=4)

@app.route('/')
def index():
    pedidos = carregar_pedidos()
    # Inverte a lista para que o pedido mais novo apareça primeiro no topo
    return render_template('index.html', pedidos=list(reversed(pedidos)))

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload:
            return jsonify({"status": "vazio"}), 200

        # Extrai os dados do Tiny
        info = payload.get('dados', payload)
        numero = str(info.get('numero', ''))
        
        # Lógica do E-commerce / Venda Direta
        ecommerce = info.get('nomeEcommerce', '').strip()
        if not ecommerce:
            ecommerce = "Venda Direta"
            
        status_bruto = str(info.get('descricaoSituacao') or info.get('codigoSituacao') or '').lower()
        
        # Tratamento do nome do cliente
        cliente_obj = info.get('cliente', {})
        if isinstance(cliente_obj, dict):
            nome_cliente = cliente_obj.get('nome', 'Cliente não identificado')
        else:
            nome_cliente = str(cliente_obj)

        if not numero:
            print(f"!!! Pedido sem número ignorado: {payload}")
            return jsonify({"status": "error", "msg": "numero nao encontrado"}), 200

        pedidos = carregar_pedidos()
        
        # Filtro de saída (Status que removem o card da tela)
        remover = ['cancelado', 'faturado', 'despachado', 'entregue', 'atendido']

        if any(s in status_bruto for s in remover):
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            print(f"--- Pedido {numero} REMOVIDO (Status: {status_bruto})")
        else:
            # Ajuste de Fuso Horário (Render UTC 0 para Brasil UTC -3)
            fuso_brasil = datetime.now() - timedelta(hours=3)
            agora = fuso_brasil.strftime('%H:%M')
            
            encontrado = False
            for p in pedidos:
                if str(p.get('numero')) == numero:
                    p['situacao'] = status_bruto.upper()
                    p['cliente_exibicao'] = nome_cliente
                    p['ecommerce'] = ecommerce
                    p['ultima_atualizacao'] = agora
                    encontrado = True
                    break
            
            if not encontrado:
                novo_pedido = {
                    "numero": numero,
                    "cliente_exibicao": nome_cliente,
                    "ecommerce": ecommerce,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora
                }
                pedidos.append(novo_pedido)
                print(f"+++ Pedido {numero} ADICIONADO via {ecommerce}")

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"ERRO NO WEBHOOK: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    # Porta padrão para o Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
