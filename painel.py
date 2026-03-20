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
        with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def salvar_pedidos(pedidos):
    with open(ARQUIVO_JSON, 'w', encoding='utf-8') as f:
        json.dump(pedidos, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    pedidos = carregar_pedidos()
    return render_template('index.html', pedidos=list(reversed(pedidos)))

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload:
            return jsonify({"status": "vazio"}), 200

        info = payload.get('dados', payload)
        numero = str(info.get('numero', ''))
        
        # Tenta capturar o valor de múltiplas chaves comuns no Tiny
        valor_bruto = info.get('total') or info.get('valor') or info.get('valor_total') or info.get('total_pedido') or 0.00
        
        try:
            valor_num = float(valor_bruto)
            valor_formatado = f"R$ {valor_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except:
            valor_formatado = "R$ 0,00"

        ecommerce = info.get('nomeEcommerce', '').strip()
        if not ecommerce:
            ecommerce = "Venda Direta"
            
        status_bruto = str(info.get('descricaoSituacao') or info.get('codigoSituacao') or '').lower()
        
        cliente_obj = info.get('cliente', {})
        nome_cliente = cliente_obj.get('nome', 'Cliente não identificado') if isinstance(cliente_obj, dict) else str(cliente_obj)

        if not numero:
            return jsonify({"status": "error"}), 200

        pedidos = carregar_pedidos()
        remover = ['cancelado', 'faturado', 'despachado', 'entregue', 'atendido']

        if any(s in status_bruto for s in remover):
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
        else:
            fuso_brasil = datetime.now() - timedelta(hours=3)
            agora = fuso_brasil.strftime('%H:%M')
            
            encontrado = False
            for p in pedidos:
                if str(p.get('numero')) == numero:
                    p['situacao'] = status_bruto.upper()
                    p['cliente_exibicao'] = nome_cliente
                    p['ecommerce'] = ecommerce
                    p['valor'] = valor_formatado
                    p['ultima_atualizacao'] = agora
                    encontrado = True
                    break
            
            if not encontrado:
                pedidos.append({
                    "numero": numero,
                    "cliente_exibicao": nome_cliente,
                    "ecommerce": ecommerce,
                    "valor": valor_formatado,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora
                })

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
