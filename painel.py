import json
import os
import logging
import sys
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

# Configuração de Log Profissional
logging.basicConfig(stream=sys.stdout, level=logging.INFO, 
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
    # LOG QUE APARECERÁ NO RENDER
    dados_brutos = request.get_data(as_text=True)
    logger.info(f"DADOS RECEBIDOS DO TINY: {dados_brutos}")

    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload: return jsonify({"status": "vazio"}), 200

        cnpj_recebido = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        slug_conta = CONTAS.get(cnpj_recebido)

        if not slug_conta:
            logger.warning(f"CNPJ {cnpj_recebido} NÃO MAPEADO")
            return jsonify({"status": "cnpj_desconhecido"}), 200

        info = payload.get('dados', payload)
        pedido = info.get('pedido', info)
        numero = str(pedido.get('numero', ''))
        status = str(pedido.get('descricaoSituacao', '')).lower()

        if "aberto" in status or "aprovado" in status:
            pedidos = carregar_dados(slug_conta)
            fuso = datetime.now() - timedelta(hours=3)
            
            # TENTATIVA DE CAPTURAR VALOR (Testando várias chaves possíveis)
            valor = pedido.get('total') or pedido.get('valor_total') or info.get('total') or "0,00"
            
            # TENTATIVA DE CAPTURAR ITENS
            itens_brutos = pedido.get('itens', [])
            produtos = []
            for i in itens_brutos:
                item_data = i.get('item', i)
                desc = item_data.get('descricao', 'Sem Nome')
                sku = item_data.get('codigo', 'S/SKU')
                qtd = int(float(item_data.get('quantidade', 1)))
                produtos.append(f"{qtd}x [{sku}] {desc}")
            
            lista_produtos = " | ".join(produtos) if produtos else "Itens não carregados - Verifique Config Webhook"

            # Formata Valor
            try:
                valor_f = f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                valor_f = f"R$ {valor}"

            # Atualiza ou Adiciona
            novo_p = {
                "numero": numero,
                "cliente": (pedido.get('cliente') or {}).get('nome', 'Cliente'),
                "ecommerce": pedido.get('nome_ecommerce') or pedido.get('nomeEcommerce') or "Venda Direta",
                "situacao": status.upper(),
                "ultima_atualizacao": fuso.strftime('%H:%M'),
                "chegada": fuso.isoformat(),
                "valor": valor_f,
                "produtos": lista_produtos
            }

            pedidos = [p for p in pedidos if str(p['numero']) != numero] # Remove duplicado
            pedidos.append(novo_p)
            salvar_dados(pedidos, slug_conta)
            logger.info(f"PEDIDO {numero} ADICIONADO/ATUALIZADO")
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"ERRO PROCESSAMENTO: {str(e)}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
