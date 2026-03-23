import json
import os
from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta

app = Flask(__name__)

# ARQUIVOS DE DADOS PARA CADA CONTA
ARQUIVOS = {
    "eracks": "pedidos_eracks.json",
    "f2": "pedidos_f2.json",
    "agrosensores": "pedidos_agro.json"
}

# CONFIGURAÇÃO DE CNPJs OFICIAIS
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
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload: return jsonify({"status": "vazio"}), 200

        # Identifica a conta e limpa o CNPJ
        cnpj_recebido = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        slug_conta = CONTAS.get(cnpj_recebido)

        if not slug_conta:
            print(f"Aviso: CNPJ {cnpj_recebido} não cadastrado.")
            return jsonify({"status": "cnpj_desconhecido"}), 200

        info = payload.get('dados', payload)
        dados_pedido = info.get('pedido', info)
        numero = str(dados_pedido.get('numero') or info.get('numero', ''))
        status_bruto = str(dados_pedido.get('descricaoSituacao') or info.get('descricaoSituacao') or '').lower()

        pedidos = carregar_dados(slug_conta)

        # Regra: Só exibe se estiver em aberto ou situações similares de início
        if "aberto" in status_bruto or "aprovado" in status_bruto:
            fuso = datetime.now() - timedelta(hours=3)
            agora_hora = fuso.strftime('%H:%M')
            chegada_iso = fuso.isoformat() # Usado para o cronómetro no HTML
            
            valor_bruto = dados_pedido.get('total') or info.get('total') or 0
            ecommerce = (dados_pedido.get('nomeEcommerce') or info.get('nomeEcommerce') or "Venda Direta").strip()
            
            # Captura de Itens (Produtos e SKUs)
            itens_lista = dados_pedido.get('itens', [])
            produtos_fmt = []
            for item in itens_lista:
                obj = item.get('item', item)
                nome_prod = obj.get('descricao', 'Produto')
                sku_prod = obj.get('codigo', 'S/SKU')
                qtd_prod = int(float(obj.get('quantidade', 1)))
                produtos_fmt.append(f"{qtd_prod}x [{sku_prod}] {nome_prod}")
            
            produtos_str = " | ".join(produtos_fmt)

            cliente_info = dados_pedido.get('cliente') or {}
            cliente = cliente_info.get('nome', 'Cliente') if isinstance(cliente_info, dict) else str(cliente_info)

            encontrado = False
            for p in pedidos:
                if str(p['numero']) == numero:
                    p['situacao'] = status_bruto.upper()
                    p['ultima_atualizacao'] = agora_hora
                    p['produtos'] = produtos_str
                    # Mantemos a 'chegada' original para o cronómetro não resetar
                    encontrado = True
                    break
            
            if not encontrado:
                valor_fmt = f"R$ {float(valor_bruto):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                pedidos.append({
                    "numero": numero,
                    "cliente": cliente,
                    "ecommerce": ecommerce,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora_hora,
                    "chegada": chegada_iso,
                    "valor": valor_fmt,
                    "produtos": produtos_str
                })
        else:
            # Remove o pedido se mudar para faturado, cancelado ou pronto para envio
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]

        salvar_dados(pedidos, slug_conta)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Erro no processamento do webhook: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    # Porta padrão para o Render ou local
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
