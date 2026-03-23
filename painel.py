import json
import os
import logging
import sys
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

# Configuração de Log para aparecer no Render
logging.basicConfig(stream=sys.stderr, level=logging.INFO, 
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

ARQUIVOS = {"eracks": "pedidos_eracks.json", "f2": "pedidos_f2.json", "agrosensores": "pedidos_agro.json"}
CONTAS = {"39544860000121": "eracks", "09653335000183": "f2", "07093835000182": "agrosensores"}

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
    # Isso força o dado bruto a aparecer no Log do Render
    dados_brutos = request.get_data(as_text=True)
    logger.info(f"DADOS DO TINY: {dados_brutos}")

    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload: return jsonify({"status": "vazio"}), 200

        cnpj = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        slug = CONTAS.get(cnpj)

        if not slug:
            logger.warning(f"CNPJ {cnpj} nao reconhecido")
            return jsonify({"status": "cnpj_desconhecido"}), 200

        # Navega no JSON do Tiny (pode vir como 'dados' ou direto)
        dados = payload.get('dados', payload)
        pedido = dados.get('pedido', dados)
        
        numero = str(pedido.get('numero') or dados.get('numero', ''))
        status = str(pedido.get('descricaoSituacao') or dados.get('descricaoSituacao') or '').lower()

        if "aberto" in status or "aprovado" in status:
            pedidos = carregar_dados(slug)
            fuso = datetime.now() - timedelta(hours=3)
            
            # Captura VALOR (tenta várias chaves comuns)
            valor = pedido.get('total') or pedido.get('valor_total') or dados.get('total') or 0
            
            # Captura ECOMMERCE
            mkt = (pedido.get('nome_ecommerce') or pedido.get('nomeEcommerce') or "Venda Direta").strip()
            
            # Captura ITENS
            itens_lista = pedido.get('itens', [])
            produtos = []
            for i in itens_lista:
                obj = i.get('item', i)
                desc = obj.get('descricao', 'Produto')
                sku = obj.get('codigo', 'S/SKU')
                qtd = int(float(obj.get('quantidade', 1)))
                produtos.append(f"{qtd}x [{sku}] {desc}")
            
            prod_str = " | ".join(produtos) if produtos else "Itens nao enviados - Veja Config Tiny"

            # Formatação de Valor
            try:
                valor_f = f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                valor_f = f"R$ {valor}"

            # Atualiza lista (evita duplicados)
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
            logger.info(f"Pedido {numero} salvo com sucesso!")
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
