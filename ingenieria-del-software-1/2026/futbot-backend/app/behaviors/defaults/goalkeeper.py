def behavior(player):
    if player.tengo_pelota():
        aliado = player.encontrar_aliado()
        player.patear_pelota(aliado)
    else:
        arco = player.encontrar_arco_aliado()
        player.correr(arco)