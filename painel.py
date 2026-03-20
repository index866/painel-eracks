from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

# Nome do arquivo de banco de dados temporário
DATA_FILE = 'pedidos_eracks.json'

def carregar_pedidos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def salvar_pedidos(pedidos):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(pedidos, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    pedidos = carregar_pedidos()
    # Garante que a lista esteja ordenada pelos mais recentes no topo
    pedidos_ordenados = sorted(pedidos, key=lambda x: x.get('data', ''), reverse=True)
    return render_template('index.html', pedidos=pedidos_ordenados)

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        # O Tiny envia os dados dentro de um formulário ou JSON direto
        dados = request.get_json()
        if not dados:
            return jsonify({"status": "erro", "message": "Sem dados"}), 400

        # Extraindo informações básicas (ajuste os nomes se o seu Tiny enviar diferente)
        numero = str(dados.get('numero', ''))
        # Convertemos para minúsculo para facilitar a comparação
        status = str(dados.get('situacao', '')).lower() 
        
        pedidos = carregar_pedidos()

        # LOGICA DE REMOÇÃO: Se for cancelado ou faturado, removemos da lista
        if status in ['cancelado', 'faturado', 'atendido', 'concluido']:
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
            print(f"Pedido {numero} removido: Status {status}")
        else:
            # LÓGICA DE ATUALIZAÇÃO: Se o pedido já existe, atualiza. Se não, adiciona.
            encontrado = False
            for p in pedidos:
                if str(p.get('numero')) == numero:
                    p.update(dados)
                    encontrado = True
                    break
            
            if not encontrado:
                pedidos.append(dados)
            print(f"Pedido {numero} atualizado/adicionado: Status {status}")

        salvar_pedidos(pedidos)
        return jsonify({"status": "sucesso"}), 200

    except Exception as e:
        print(f"Erro no Webhook: {e}")
        return jsonify({"status": "erro", "message": str(e)}), 500

if __name__ == '__main__':
    # Porta padrão do Render é 10000, mas o Gunicorn cuida disso
    app.run(host='0.0.0.0', port=5000)
