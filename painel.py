import json
import os
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuração dos CNPJs de cada conta (Preencha com os CNPJs corretos do seu Tiny)
CONTAS = {
    "39544860000121": "eracks", # CNPJ da Eracks (visto no seu log)
    "00000000000000": "f2",     # COLOQUE O CNPJ DA CONTA F2 AQUI
    "11111111111111": "agrosensores" # COLOQUE O CNPJ DA AGROSENSORES AQUI
}

def carregar_dados(conta):
    arquivo = f'pedidos_{conta}.json'
    if not os.path.exists(arquivo): return []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def salvar_dados(dados, conta):
    arquivo = f'pedidos_{conta}.json'
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    return render_template('index.html', 
                           eracks=list(reversed(carregar_dados("eracks"))),
                           f2=list(reversed(carregar_dados("f2"))),
                           agrosensores=list(reversed(carregar_dados("agrosensores"))))

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload: return jsonify({"status": "vazio"}), 200

        # Identifica de qual conta vem o pedido pelo CNPJ
        cnpj_recebido = str(payload.get('cnpj', ''))
        slug_conta = CONTAS.get(cnpj_recebido)

        if not slug_conta:
            print(f"CNPJ {cnpj_recebido} não cadastrado no painel.")
            return jsonify({"status": "cnpj_desconhecido"}), 200

        info = payload.get('dados', payload)
        dados_pedido = info.get('pedido', info)
        numero = str(dados_pedido.get('numero') or info.get('numero', ''))
        status_bruto = str(dados_pedido.get('descricaoSituacao') or info.get('descricaoSituacao') or '').lower()

        pedidos = carregar_dados(slug_conta)

        if "aberto" in status_bruto:
            fuso = datetime.now() - timedelta(hours=3)
            agora = fuso.strftime('%H:%M')
            
            valor_bruto = dados_pedido.get('total') or info.get('total') or 0
            ecommerce = (dados_pedido.get('nomeEcommerce') or info.get('nomeEcommerce') or "Venda Direta").strip()
            cliente = (dados_pedido.get('cliente', {})).get('nome', 'Cliente')

            encontrado = False
            for p in pedidos:
                if str(p['numero']) == numero:
                    p['situacao'] = status_bruto.upper()
                    p['ultima_atualizacao'] = agora
                    if float(valor_bruto) > 0: p['valor'] = f"R$ {float(valor_bruto):,.2f}"
                    encontrado = True
                    break
            
            if not encontrado:
                pedidos.append({
                    "numero": numero,
                    "cliente": cliente,
                    "ecommerce": ecommerce,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora,
                    "valor": f"R$ {float(valor_bruto):,.2f}" if float(valor_bruto) > 0 else "---"
                })
        else:
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]

        salvar_dados(pedidos, slug_conta)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    # O Render define a variável de ambiente PORT automaticamente
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
