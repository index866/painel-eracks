from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
DATA_FILE = 'pedidos_eracks.json'

def carregar_pedidos():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_pedidos(pedidos):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(pedidos, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    pedidos = carregar_pedidos()
    # Ordena para o mais recente ficar no topo
    pedidos_ordenados = sorted(pedidos, key=lambda x: x.get('ultima_atualizacao', ''), reverse=True)
    return render_template('index.html', pedidos=pedidos_ordenados)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        # Pega os dados brutos para não perder nada
        dados = request.get_json(silent=True) or request.form.to_dict()
        
        if not dados:
            print("!!! Recebi um post, mas veio sem dados.")
            return jsonify({"status": "error", "msg": "Sem dados"}), 200

        # Tenta encontrar o NÚMERO do pedido em qualquer lugar (numero ou numero_pedido)
        numero = str(dados.get('numero') or dados.get('numero_pedido') or '')
        
        # Tenta encontrar a SITUAÇÃO/STATUS
        status_bruto = str(dados.get('situacao') or dados.get('status') or '').lower()
        
        # Tenta encontrar o NOME do cliente (pode vir como string ou dentro de um objeto)
        cliente_raw = dados.get('cliente', 'Cliente não identificado')
        if isinstance(cliente_raw, dict):
            nome_cliente = cliente_raw.get('nome', 'Cliente s/ nome')
        else:
            nome_cliente = str(cliente_raw)

        # Se não achou número, não tem como salvar
        if not numero or numero == "":
            print(f"!!! Pedido ignorado: não achei o campo 'numero'. Dados: {dados}")
            return jsonify({"status": "error", "msg": "numero nao encontrado"}), 200

        pedidos = carregar_pedidos()

        # LISTA DE REMOÇÃO (Se o status for um destes, o pedido SOME da tela)
        # Removi 'atendido' e 'concluido' temporariamente para teste
        remover = ['cancelado', 'faturado', 'despachado', 'entregue']

        if any(s in status_bruto for s in remover):
            # Filtra a lista e tira o pedido com esse número
            pedidos = [p for p in pedidos if str(p.get('numero') or p.get('numero_pedido')) != numero]
            print(f"--- Pedido {numero} REMOVIDO (Status: {status_bruto})")
        else:
            # Se NÃO for status de remover, ele entra ou atualiza na tela
            agora = datetime.now().strftime('%H:%M')
            encontrado = False
            
            for p in pedidos:
                if str(p.get('numero') or p.get('numero_pedido')) == numero:
                    p.update(dados) # Atualiza com os dados novos do Tiny
                    p['cliente_exibicao'] = nome_cliente
                    p['ultima_atualizacao'] = agora
                    p['situacao_exibicao'] = status_bruto.upper()
                    encontrado = True
                    break
            
            if not encontrado:
                # Se for pedido novo, cria o registro
                novo_pedido = {
                    "numero": numero,
                    "cliente_exibicao": nome_cliente,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora
                }
                pedidos.append(novo_pedido)
            
            print(f"+++ Pedido {numero} NA TELA (Status: {status_bruto})")

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"ERRO CRÍTICO: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
