"""Excepciones del modulo de comportamientos."""
 
 
class ComportamientoNoEncontrado(Exception):
    """El behavior_id pedido no esta cargado en el cache en memoria.
 
    Puede pasar por un id inexistente, o por pedir un comportamiento
    de club en un momento en el que este modulo todavia solo precarga
    los preprogramados (is_preprogrammed=True).
    """
 
 
class ComportamientoInvalido(Exception):
    """El codigo de un comportamiento no define una funcion `comportamiento`
    invocable. Se levanta al precargar, no en cada tick, para fallar rapido
    al arrancar el server en vez de silenciosamente durante un partido.
    """
 