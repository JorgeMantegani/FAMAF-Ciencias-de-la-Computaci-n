def behavior(player):
    if player.tengo_pelota():
        arco = player.encontrar_arco_enemigo()
        player.patear_pelota(arco)
        
    else:
        pelota = player.encontrar_pelota()
        player.correr(pelota)