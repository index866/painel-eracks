import sys # Adicione isso no topo do arquivo junto com os outros imports

@app.route('/webhook-tiny', methods=['POST'])
def webhook_tiny():
    # Força a exibição imediata no log do Render
    payload = request.get_json(silent=True) or request.form.to_dict()
    print(f"--- NOVO WEBHOOK RECEBIDO ---", flush=True)
    print(f"CONTEUDO: {json.dumps(payload)}", flush=True)
    sys.stdout.flush() # Garante que o log saia do sistema para a tela

    try:
        if not payload: return jsonify({"status": "vazio"}), 200

        cnpj_recebido = str(payload.get('cnpj', '')).replace('.', '').replace('/', '').replace('-', '').strip()
        slug_conta = CONTAS.get(cnpj_recebido)

        if not slug_conta:
            return jsonify({"status": "cnpj_desconhecido"}), 200

        info = payload.get('dados', payload)
        dados_pedido = info.get('pedido', info)
        numero = str(dados_pedido.get('numero') or info.get('numero', ''))
        status_bruto = str(dados_pedido.get('descricaoSituacao') or info.get('descricaoSituacao') or '').lower()

        pedidos = carregar_dados(slug_conta)

        if "aberto" in status_bruto or "aprovado" in status_bruto:
            fuso = datetime.now() - timedelta(hours=3)
            agora_hora = fuso.strftime('%H:%M')
            chegada_iso = fuso.isoformat()
            
            # Tenta capturar o VALOR de várias chaves possíveis do Tiny
            valor_bruto = dados_pedido.get('total') or dados_pedido.get('valor_total') or info.get('total') or 0
            
            # Tenta capturar o ECOMMERCE
            ecommerce = (dados_pedido.get('nome_ecommerce') or dados_pedido.get('nomeEcommerce') or "Venda Direta").strip()
            
            # Tenta capturar ITENS
            itens_lista = dados_pedido.get('itens', [])
            produtos_fmt = []
            for item in itens_lista:
                # O Tiny às vezes envia como {'item': {...}} ou direto {...}
                obj = item.get('item', item)
                nome_prod = obj.get('descricao', obj.get('nome', 'Produto'))
                sku_prod = obj.get('codigo', obj.get('sku', 'S/SKU'))
                qtd_prod = int(float(obj.get('quantidade', 1)))
                produtos_fmt.append(f"{qtd_prod}x [{sku_prod}] {nome_prod}")
            
            produtos_str = " | ".join(produtos_fmt) if produtos_fmt else "Itens não enviados pelo Tiny"
            
            cliente_info = dados_pedido.get('cliente') or {}
            cliente = cliente_info.get('nome', 'Cliente') if isinstance(cliente_info, dict) else str(cliente_info)

            # Atualiza ou Adiciona
            encontrado = False
            valor_final = f"R$ {float(valor_bruto):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            for p in pedidos:
                if str(p['numero']) == numero:
                    p['situacao'] = status_bruto.upper()
                    p['ultima_atualizacao'] = agora_hora
                    p['produtos'] = produtos_str
                    p['valor'] = valor_final
                    encontrado = True
                    break
            
            if not encontrado:
                pedidos.append({
                    "numero": numero,
                    "cliente": cliente,
                    "ecommerce": ecommerce,
                    "situacao": status_bruto.upper(),
                    "ultima_atualizacao": agora_hora,
                    "chegada": chegada_iso,
                    "valor": valor_final,
                    "produtos": produtos_str
                })
        else:
            pedidos = [p for p in pedidos if str(p.get('numero')) != numero]

        salvar_dados(pedidos, slug_conta)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"ERRO: {e}", flush=True)
        return jsonify({"status": "error"}), 200
