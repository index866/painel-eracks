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

        print(f"DEBUG PAYLOAD: {payload}")

        info = payload.get('dados', payload)
        dados_pedido = info.get('pedido', info)
        numero = str(dados_pedido.get('numero') or info.get('numero', ''))
        
        # Captura do Valor
        valor_bruto = (
            dados_pedido.get('total') or 
            dados_pedido.get('valor') or 
            info.get('total') or 0.00
        )
        
        try:
            valor_num = float(valor_bruto)
            valor_formatado = f"R$ {valor_num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except:
            valor_formatado = "R$ 0,00"

        ecommerce = (dados_pedido.get('nomeEcommerce') or info.get('nomeEcommerce', 'Venda Direta')).strip()
        
        # Status vindo do Tiny
        status_bruto = str(dados_pedido.get('descricaoSituacao') or info.get('descricaoSituacao') or '').lower()
        
        cliente_obj = dados_pedido.get('cliente') or info.get('cliente', {})
        nome_cliente = cliente_obj.get('nome', 'Cliente não identificado') if isinstance(cliente_obj, dict) else str(cliente_obj)

        if not numero or numero == 'None':
            return jsonify({"status": "error"}), 200

        pedidos = carregar_pedidos()

        # NOVA LÓGICA DE FILTRO:
        # Só entra na tela se o status contiver "aberto"
        if "aberto" in status_bruto:
            fuso_brasil = datetime.now() - timedelta(hours=3)
            agora = fuso_brasil.strftime('%H:%M')
            
            encontrado = False
            for p in pedidos:
                if str(p.get('numero')) == numero:
                    p['situacao'] = status_bruna_upper = status_bruto.upper()
                    p['cliente_exibicao'] = nome_cliente
                    p['ecommerce'] = ecommerce
                    # Preserva o valor caso o webhook de atualização venha zerado
                    if valor_num > 0:
                        p['valor'] = valor_formatado
                    p['ultima_atualizacao'] = agora
                    encontrado = True
                    break
            
            if not encontrado:
                pedidos.append({
                    "numero": numero,
                    "cliente_exibicao": nome_cliente,
                    "ecommerce": ecommerce,
                    "valor": valor_formatado if valor_num > 0 else "---",
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora
                })
        else:
            # Se o status for QUALQUER OUTRO (Pronto para envio, Faturado, etc), removemos da lista
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            print(f"--- Pedido {numero} REMOVIDO (Status: {status_bruto})")

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"status": "error"}), 200

@app.route('/ping')
def ping():
    return "Acordado!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
