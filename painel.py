import json
import os
import logging
import sys
import requests
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# =========================================================
# CONFIGURAÇÃO MULTI-EMPRESA (TOKENS E ARQUIVOS)
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
        "token": "COLOQUE_AQUI_O_TOKEN_DA_F2" 
    },
    "07093835000182": {
        "slug": "agrosensores",
        "arquivo": "pedidos_agro.json",
        "token": "COLOQUE_AQUI_O_TOKEN_DA_AGRO"
    }
}

def buscar_estoque(sku, token):
    """ Consulta o saldo atual do produto no Tiny """
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
    """ Consulta Detalhes, Marketplace e Estoque de cada item """
    url = "https://api.tiny.com.br/api2/pedido.obter.php"
    params = {'token': token, 'id': id_pedido, 'formato': 'json'}
    try:
        res = requests.get(url, params=params, timeout=10)
        dados = res.json()
        retorno = dados.get('retorno', {})
        if retorno.get('status') == 'OK':
            p = retorno.get('pedido', {})
            
            # Tenta encontrar o marketplace em vários campos possíveis
            mkt = p.get('nome_ecommerce') or p.get('nome_omnichannel') or p.get('id_venda_original') or "Venda Direta"
            if not mkt or mkt == "": mkt = "Venda Direta"

            itens = p.get('itens', [])
            lista_prod = []
            for i in itens:
                item = i.get('item', {})
                sku = item.get('codigo', 'S/SKU')
                desc = item.get('descricao', 'Produto')
                qtd_pedida = int(float(item.get('quantidade', 1)))
                
                # BUSCA ESTOQUE REAL NO MOMENTO
                saldo_atual = buscar_estoque(sku, token)
                status_estoque = f"✅ Disp: {int(saldo_atual)}" if saldo_atual >= qtd_pedida else f"❌ Falta (Estoque: {int(saldo_atual)})"
                
                lista_prod.append(f"{qtd_pedida}x [{sku}] {desc} | {status_estoque}")
            
            return {
                "valor": p.get('total_pedido', 0),
                "mkt": mkt,
                "produtos": " <br> ".join(lista_prod) # Usando <br> para quebrar linha no card
            }
    except Exception as e:
        logger.error(f"Erro na consulta API Tiny: {e}")
    return None

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
    return render_template('index.html', 
                           eracks=list(reversed(carregar_dados("pedidos_eracks.json"))),
                           f2=list(reversed(carregar_dados("pedidos_f2.json"))),
                           agrosensores=list(reversed(carregar_dados("pedidos_agro.json"))))

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    payload = request.get_json(silent=True) or request.form.to_dict()
    if not payload or payload.get('tipo') == 'estoque': return jsonify({"status": "ignorado"}), 200

    try:
        cnpj = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        config = CONFIG_EMPRESAS.get(cnpj)
        if not config: return jsonify({"status": "cnpj_desconhecido"}), 200

        dados_webhook = payload.get('dados', {})
        id_pedido = dados_webhook.get('id')
        numero = str(dados_webhook.get('numero', ''))
        status = str(dados_webhook.get('descricaoSituacao', '')).lower()

        arquivo_destino = config['arquivo']
        pedidos = carregar_dados(arquivo_destino)
        
        situacoes_vivas = ["aberto", "aprovado", "preparando", "pronto", "separacao"]
        
        if any(x in status for x in situacoes_vivas):
            detalhes = buscar_detalhes_tiny(id_pedido, config['token'])
            
            fuso = datetime.now() - timedelta(hours=3)
            valor_raw = detalhes['valor'] if detalhes else 0
            valor_f = f"R$ {float(valor_raw):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            pedidos.append({
                "numero": numero,
                "cliente": dados_webhook.get('cliente', {}).get('nome', 'Cliente'),
                "ecommerce": detalhes['mkt'] if detalhes else "Venda Direta",
                "situacao": status.upper(),
                "ultima_atualizacao": fuso.strftime('%H:%M'),
                "chegada": fuso.isoformat(),
                "valor": valor_f,
                "produtos": detalhes['produtos'] if detalhes else "Consultando itens..."
            })
        else:
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]

        salvar_dados(pedidos, arquivo_destino)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
