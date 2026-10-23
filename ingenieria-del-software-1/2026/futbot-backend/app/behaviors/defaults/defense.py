def behavior(player):
    if player.tengo_pelota():
        aliado = player.encontrar_aliado()
        player.patear_pelota(aliado)
    else:
        pelota = player.encontrar_pelota()
        player.correr(pelota)