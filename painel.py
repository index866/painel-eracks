import json
import os
import logging
import sys
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

# 1. Configuração de Log (Para aparecer no Render)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, 
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 2. Definição do App (CORREÇÃO DO ERRO)
app = Flask(__name__)

# Configurações de arquivos e contas
ARQUIVOS = {
    "eracks": "pedidos_eracks.json",
    "f2": "pedidos_f2.json",
    "agrosensores": "pedidos_agro.json"
}

CONTAS = {
    "39544860000121": "eracks",
    "09653335000183": "f2",
    "07093835000182": "agrosensores"
}

def carregar_dados(slug):
    arquivo = ARQUIVOS.get(slug)
    if not arquivo or not os.path.exists(arquivo): return []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def salvar_dados(dados, slug):
    arquivo = ARQUIVOS.get(slug)
    if arquivo:
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
    # Isso vai mostrar exatamente o que o Tiny enviou nos logs do Render
    dados_brutos = request.get_data(as_text=True)
    logger.info(f"DADOS RECEBIDOS: {dados_brutos}")

    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload: return jsonify({"status": "vazio"}), 200

        cnpj_recebido = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        slug_conta = CONTAS.get(cnpj_recebido)

        if not slug_conta:
            logger.warning(f"CNPJ {cnpj_recebido} desconhecido")
            return jsonify({"status": "cnpj_desconhecido"}), 200

        info = payload.get('dados', payload)
        pedido_data = info.get('pedido', info)
        numero = str(pedido_data.get('numero') or info.get('numero', ''))
        status_bruto = str(pedido_data.get('descricaoSituacao') or info.get('descricaoSituacao') or '').lower()

        pedidos = carregar_dados(slug_conta)

        if "aberto" in status_bruto or "aprovado" in status_bruto:
            fuso = datetime.now() - timedelta(hours=3)
            
            # Captura valor e itens
            valor_bruto = pedido_data.get('total') or info.get('total') or 0
            ecommerce = (pedido_data.get('nome_ecommerce') or pedido_data.get('nomeEcommerce') or "Venda Direta").strip()
            
            itens_lista = pedido_data.get('itens', [])
            produtos_fmt = []
            for item in itens_lista:
                obj = item.get('item', item)
                desc = obj.get('descricao', 'Produto')
                sku = obj.get('codigo', 'S/SKU')
                qtd = int(float(obj.get('quantidade', 1)))
                produtos_fmt.append(f"{qtd}x [{sku}] {desc}")
            
            produtos_str = " | ".join(produtos_fmt) if produtos_fmt else "Itens não carregados - Verifique o Tiny"
            cliente_info = pedido_data.get('cliente') or {}
            nome_cliente = cliente_info.get('nome', 'Cliente') if isinstance(cliente_info, dict) else str(cliente_info)

            # Formata valor para R$
            try:
                valor_f = f"R$ {float(valor_bruto):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                valor_f = f"R$ {valor_bruto}"

            # Remove pedido antigo se já existir para não duplicar
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            
            pedidos.append({
                "numero": numero,
                "cliente": nome_cliente,
                "ecommerce": ecommerce,
                "situacao": status_bruto.upper(),
                "ultima_atualizacao": fuso.strftime('%H:%M'),
                "chegada": fuso.isoformat(),
                "valor": valor_f,
                "produtos": produtos_str
            })
        else:
            # Remove o pedido se ele não estiver mais em aberto/aprovado
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]

        salvar_dados(pedidos, slug_conta)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
