@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not payload:
            return jsonify({"status": "vazio"}), 200

        info = payload.get('dados', payload)
        numero = str(info.get('numero', ''))
        status_bruto = str(info.get('descricaoSituacao') or info.get('codigoSituacao') or '').lower()
        
        cliente_obj = info.get('cliente', {})
        nome_cliente = cliente_obj.get('nome', 'Cliente não identificado') if isinstance(cliente_obj, dict) else str(cliente_obj)

        if not numero:
            return jsonify({"status": "error", "msg": "numero nao encontrado"}), 200

        pedidos = carregar_pedidos()
        remover = ['cancelado', 'faturado', 'despachado', 'entregue', 'atendido']

        if any(s in status_bruto for s in remover):
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]
        else:
            # --- AJUSTE DE HORÁRIO AQUI ---
            fuso_brasil = datetime.now() - timedelta(hours=3)
            agora = fuso_brasil.strftime('%H:%M')
            # ------------------------------
            
            encontrado = False
            for p in pedidos:
                if str(p.get('numero')) == numero:
                    p['situacao'] = status_bruto.upper()
                    p['cliente_exibicao'] = nome_cliente
                    p['ultima_atualizacao'] = agora
                    encontrado = True
                    break
            
            if not encontrado:
                novo_pedido = {
                    "numero": numero,
                    "cliente_exibicao": nome_cliente,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora
                }
                pedidos.append(novo_pedido)

        salvar_pedidos(pedidos)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"ERRO: {e}")
        return jsonify({"status": "error"}), 200
