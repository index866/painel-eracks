import json
import os
import logging
import sys
import requests
import re
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

# Configuração de Log
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# =========================================================
# CONFIGURAÇÃO MULTI-EMPRESA
# =========================================================
CONFIG_EMPRESAS = {
    "39544860000121": {
        "slug": "eracks",
        "arquivo": "pedidos_eracks.json",
        "token": "e8cfcc618814f39c97a3594f2ed3e6829a758dc4"
    },
    "09653335000183": {
        "slug": "f2",
        "arquivo": "pedidos_f2.json",
        "token": "642e5d6355abd64b35a6bf6d871b5608db1647ca" 
    },
    "07093835000182": {
        "slug": "agrosensores",
        "arquivo": "pedidos_agro.json",
        "token": "db584433551951c62935da579bd65b9031d3e919"
    }
}

def buscar_estoque(sku, token):
    url = "https://api.tiny.com.br/api2/produto.obter.estoque.php"
    params = {'token': token, 'codigo': sku, 'formato': 'json'}
    try:
        res = requests.get(url, params=params, timeout=5)
        dados = res.json()
        saldo = dados.get('retorno', {}).get('produto', {}).get('saldo', 0)
        return float(saldo)
    except:
        return 0

def buscar_detalhes_tiny(id_pedido, token):
    url = "https://api.tiny.com.br/api2/pedido.obter.php"
    params = {'token': token, 'id': id_pedido, 'formato': 'json'}
    try:
        res = requests.get(url, params=params, timeout=10)
        dados = res.json()
        retorno = dados.get('retorno', {})
        if retorno.get('status') == 'OK':
            p = retorno.get('pedido', {})
            mkt = (p.get('nome_ecommerce') or p.get('nome_omnichannel') or 
                   p.get('intermediador', {}).get('nome') or p.get('canal_venda') or "")
            if not mkt:
                venda_orig = str(p.get('id_venda_original', ''))
                mkt = "MERCADO LIVRE" if "MLB" in venda_orig else "VENDA DIRETA"

            itens = p.get('itens', [])
            lista_prod = []
            for i in itens:
                item = i.get('item', {})
                sku, desc = item.get('codigo', 'S/SKU'), item.get('descricao', 'Produto')
                qtd_pedida = int(float(item.get('quantidade', 1)))
                saldo_atual = buscar_estoque(sku, token)
                cor = "#2e7d32" if saldo_atual >= qtd_pedida else "#d32f2f"
                status_est = f'✅ Disp: {int(saldo_atual)}' if saldo_atual >= qtd_pedida else f'❌ FALTA: {int(saldo_atual)}'
                lista_prod.append(f"<b>{qtd_pedida}x</b> [{sku}] {desc}<br><span style='color:{cor};font-weight:bold;'>{status_est}</span>")
            
            return {"valor": p.get('total_pedido', 0), "mkt": mkt.upper(), "produtos": "<br><br>".join(lista_prod)}
    except:
        return None

def gerar_sugestoes_compra():
    sugestoes = {"ERACKS": [], "F2": [], "AGRO": []}
    vistos = set()
    mapeamento = [
        ("pedidos_eracks.json", "39544860000121", "ERACKS"), 
        ("pedidos_f2.json", "09653335000183", "F2"), 
        ("pedidos_agro.json", "07093835000182", "AGRO")
    ]
    for arq, cnpj, nome_empresa in mapeamento:
        pedidos = carregar_dados(arq)
        token = CONFIG_EMPRESAS[cnpj]['token']
        for p in pedidos:
            skus = re.findall(r"\[(.*?)\]", p.get('produtos', ''))
            for sku in skus:
                chave = f"{nome_empresa}_{sku}"
                if chave not in vistos:
                    estoque = buscar_estoque(sku, token)
                    if estoque <= 1: # ESTOQUE MÍNIMO: 1
                        sugestoes[nome_empresa].append({"sku": sku, "estoque": int(estoque)})
                    vistos.add(chave)
    return sugestoes

def carregar_dados(arquivo):
    if not os.path.exists(arquivo): return []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def salvar_dados(dados, arquivo):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    sugestoes = gerar_sugestoes_compra()
    return render_template('index.html', 
                           eracks=list(reversed(carregar_dados("pedidos_eracks.json"))),
                           f2=list(reversed(carregar_dados("pedidos_f2.json"))),
                           agrosensores=list(reversed(carregar_dados("pedidos_agro.json"))),
                           sugestoes=sugestoes)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    payload = request.get_json(silent=True) or request.form.to_dict()
    if not payload or payload.get('tipo') == 'estoque': return jsonify({"status": "ok"}), 200
    try:
        cnpj = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        config = CONFIG_EMPRESAS.get(cnpj)
        if not config: return jsonify({"status": "cnpj_erro"}), 200
        dados_webhook = payload.get('dados', {})
        id_pedido, numero = dados_webhook.get('id'), str(dados_webhook.get('numero', ''))
        status = str(dados_webhook.get('descricaoSituacao', '')).lower()
        pedidos = carregar_dados(config['arquivo'])
        pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
        if status == "aberto":
            detalhes = buscar_detalhes_tiny(id_pedido, config['token'])
            fuso = datetime.now() - timedelta(hours=3)
            valor_f = f"R$ {float(detalhes['valor'] if detalhes else 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            pedidos.append({
                "numero": numero, "cliente": dados_webhook.get('cliente', {}).get('nome', 'Cliente'),
                "ecommerce": detalhes['mkt'] if detalhes else "VENDA DIRETA", "situacao": "ABERTO",
                "chegada": fuso.isoformat(), "valor": valor_f, "produtos": detalhes['produtos'] if detalhes else "Consultando..."
            })
        salvar_dados(pedidos, config['arquivo'])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Erro: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
