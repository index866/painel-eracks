import json
import os
import logging
import sys
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

ARQUIVOS = {"eracks": "pedidos_eracks.json", "f2": "pedidos_f2.json", "agrosensores": "pedidos_agro.json"}
CONTAS = {"39544860000121": "eracks", "09653335000183": "f2", "07093835000182": "agrosensores"}

# Rota para evitar erro 404 de sistemas de monitoramento (Ping)
@app.route('/ping')
def ping():
    return "OK", 200

def carregar_dados(slug):
    arquivo = ARQUIVOS.get(slug)
    if not arquivo or not os.path.exists(arquivo): return []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def salvar_dados(dados, slug):
    arquivo = ARQUIVOS.get(slug)
    if arquivo:
        with open(arquivo, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    return render_template('index.html', 
                           eracks=list(reversed(carregar_dados("eracks"))),
                           f2=list(reversed(carregar_dados("f2"))),
                           agrosensores=list(reversed(carregar_dados("agrosensores"))))

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    # Se o Tiny enviar um teste vazio, respondemos OK para ele validar a URL
    if not request.data:
        return jsonify({"status": "conexao_ok"}), 200

    dados_brutos = request.get_data(as_text=True)
    logger.info(f"DADOS RECEBIDOS: {dados_brutos}")

    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        cnpj = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        slug = CONTAS.get(cnpj)

        if not slug:
            return jsonify({"status": "cnpj_desconhecido"}), 200

        dados = payload.get('dados', payload)
        pedido = dados.get('pedido', dados)
        
        numero = str(pedido.get('numero') or dados.get('numero', ''))
        status = str(pedido.get('descricaoSituacao') or dados.get('descricaoSituacao') or '').lower()

        # Filtro de Situações (Adicionado 'faturado' e 'pronto_envio' para teste)
        situacoes_validas = ["aberto", "aprovado", "preparando_envio", "faturado", "pronto_envio"]
        
        if any(x in status for x in situacoes_validas):
            pedidos = carregar_dados(slug)
            fuso = datetime.now() - timedelta(hours=3)
            
            # Valor (Na v3 o campo é 'total')
            valor = pedido.get('total') or dados.get('total') or 0
            
            # Marketplace (Na v3 o campo é 'nome_ecommerce')
            mkt = (pedido.get('nome_ecommerce') or pedido.get('nomeEcommerce') or "Venda Direta").strip()
            
            # Itens (Apenas na v3)
            itens_lista = pedido.get('itens', [])
            produtos = []
            for i in itens_lista:
                obj = i.get('item', i)
                desc = obj.get('descricao', 'Produto')
                sku = obj.get('codigo', 'S/SKU')
                qtd = int(float(obj.get('quantidade', 1)))
                produtos.append(f"{qtd}x [{sku}] {desc}")
            
            prod_str = " | ".join(produtos) if produtos else "Aguardando Itens (v3 necessário)"

            valor_f = f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            pedidos.append({
                "numero": numero,
                "cliente": (pedido.get('cliente') or {}).get('nome', 'Cliente'),
                "ecommerce": mkt,
                "situacao": status.upper(),
                "ultima_atualizacao": fuso.strftime('%H:%M'),
                "chegada": fuso.isoformat(),
                "valor": valor_f,
                "produtos": prod_str
            })
            salvar_dados(pedidos, slug)
        else:
            # Se mudar para um status que não queremos, remove da tela
            pedidos = carregar_dados(slug)
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            salvar_dados(pedidos, slug)
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
