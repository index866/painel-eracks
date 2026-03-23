import json
import os
import logging
import sys
import requests
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

# Configuração de Log para o Render
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
    """ Consulta o saldo atual do produto no Tiny via API """
    url = "https://api.tiny.com.br/api2/produto.obter.estoque.php"
    params = {'token': token, 'codigo': sku, 'formato': 'json'}
    try:
        res = requests.get(url, params=params, timeout=5)
        dados = res.json()
        saldo = dados.get('retorno', {}).get('produto', {}).get('saldo', 0)
        return float(saldo)
    except Exception as e:
        logger.error(f"Erro ao buscar estoque SKU {sku}: {e}")
        return 0

def buscar_detalhes_tiny(id_pedido, token):
    """ Consulta Detalhes, Marketplace e Estoque de cada item via API v2 """
    url = "https://api.tiny.com.br/api2/pedido.obter.php"
    params = {'token': token, 'id': id_pedido, 'formato': 'json'}
    try:
        res = requests.get(url, params=params, timeout=10)
        dados = res.json()
        retorno = dados.get('retorno', {})
        if retorno.get('status') == 'OK':
            p = retorno.get('pedido', {})
            
            # --- LÓGICA REFORÇADA PARA MARKETPLACE ---
            # Tenta encontrar o canal em campos que a v1 do webhook ignora
            mkt = (
                p.get('nome_ecommerce') or 
                p.get('nome_omnichannel') or 
                p.get('intermediador', {}).get('nome') or 
                p.get('canal_venda') or
                ""
            )

            # Identificação por padrão de ID (Caso os campos acima falhem)
            if not mkt or mkt == "":
                venda_orig = str(p.get('id_venda_original', ''))
                if "MLB" in venda_orig:
                    mkt = "Mercado Livre"
                elif "shopee" in venda_orig.lower():
                    mkt = "Shopee"
                else:
                    mkt = "Venda Direta"

            itens = p.get('itens', [])
            lista_prod = []
            for i in itens:
                item = i.get('item', {})
                sku = item.get('codigo', 'S/SKU')
                desc = item.get('descricao', 'Produto')
                qtd_pedida = int(float(item.get('quantidade', 1)))
                
                # BUSCA ESTOQUE REAL NO TINY
                saldo_atual = buscar_estoque(sku, token)
                
                # Define cor visual (Verde para OK, Vermelho para Falta)
                if saldo_atual >= qtd_pedida:
                    status_estoque = f'<span style="color: #2e7d32; font-weight: bold;">✅ Disponível: {int(saldo_atual)}</span>'
                else:
                    status_estoque = f'<span style="color: #d32f2f; font-weight: bold;">❌ FALTA (Estoque: {int(saldo_atual)})</span>'
                
                lista_prod.append(f"<b>{qtd_pedida}x</b> [{sku}] {desc}<br>{status_estoque}")
            
            return {
                "valor": p.get('total_pedido', 0),
                "mkt": mkt.upper(),
                "produtos": "<br><br>".join(lista_prod)
            }
    except Exception as e:
        logger.error(f"Erro na consulta API Tiny Detalhes: {e}")
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
    # Suporte para ping de teste do Tiny
    if not request.data: return jsonify({"status": "ok"}), 200

    payload = request.get_json(silent=True) or request.form.to_dict()
    
    # Ignora webhooks de alteração de estoque para não poluir o painel de vendas
    if payload.get('tipo') == 'estoque':
        return jsonify({"status": "estoque_ignorado"}), 200

    try:
        cnpj = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        config = CONFIG_EMPRESAS.get(cnpj)

        if not config:
            logger.warning(f"CNPJ {cnpj} não configurado.")
            return jsonify({"status": "cnpj_desconhecido"}), 200

        dados_webhook = payload.get('dados', {})
        id_pedido = dados_webhook.get('id')
        numero = str(dados_webhook.get('numero', ''))
        status = str(dados_webhook.get('descricaoSituacao', '')).lower()

        arquivo_destino = config['arquivo']
        pedidos = carregar_dados(arquivo_destino)
        
        # Status que devem aparecer no painel (ajuste conforme seu fluxo no Tiny)
        situacoes_vivas = ["aberto", "aprovado", "preparando", "pronto", "separacao"]
        
        if any(x in status for x in situacoes_vivas):
            # Chama a função de investigação (Marketplace + Itens + Estoque)
            detalhes = buscar_detalhes_tiny(id_pedido, config['token'])
            
            fuso = datetime.now() - timedelta(hours=3)
            valor_raw = detalhes['valor'] if detalhes else 0
            valor_f = f"R$ {float(valor_raw):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            # Remove duplicata antes de adicionar a versão atualizada
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            pedidos.append({
                "numero": numero,
                "cliente": dados_webhook.get('cliente', {}).get('nome', 'Cliente'),
                "ecommerce": detalhes['mkt'] if detalhes else "VENDA DIRETA",
                "situacao": status.upper(),
                "ultima_atualizacao": fuso.strftime('%H:%M'),
                "chegada": fuso.isoformat(),
                "valor": valor_f,
                "produtos": detalhes['produtos'] if detalhes else "Carregando informações..."
            })
            logger.info(f"Pedido {numero} da {config['slug']} atualizado com sucesso.")
        else:
            # Se o pedido foi cancelado ou faturado, removemos da visualização ativa
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]

        salvar_dados(pedidos, arquivo_destino)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Erro geral no webhook: {str(e)}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    # Porta padrão do Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
