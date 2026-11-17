import pytest
from app.behaviors.validator import validate, BehaviorValidationError, BehaviorTimeoutError


def test_codigo_valido_pasa_la_validacion():
  safe_code = """
def behavior(player):
    player.correr((10, 10))
"""
  # No debería lanzar ninguna excepción
  validate(safe_code)

def test_codigo_con_importacion_lanza_excepcion():
  unsafe_code = """
import os
def behavior(player):
    player.correr((10, 10))
"""
  with pytest.raises(BehaviorValidationError):
      validate(unsafe_code)

def test_codigo_con_bucle_infinito_lanza_excepcion():
  unsafe_code = """
def behavior(player):
    while True:
        player.correr((10, 10))
"""
  with pytest.raises(BehaviorTimeoutError):
      validate(unsafe_code)

def test_codigo_sin_funcion_behavior_lanza_excepcion():
  unsafe_code = """
def not_behavior(player):
    player.correr((10, 10))
"""
  with pytest.raises(BehaviorValidationError):
      validate(unsafe_code) 

def test_codigo_con_funcion_prohibida_lanza_excepcion():
  unsafe_code = """
def behavior(player):
    eval("print('Hola')")
"""
  with pytest.raises(BehaviorValidationError):
      validate(unsafe_code)

def test_codigo_con_acceso_a_atributos_prohibidos_lanza_excepcion():
  unsafe_code = """
def behavior(player):
    player.__dict__['hack'] = True
"""
  with pytest.raises(BehaviorValidationError):
      validate(unsafe_code)

def test_codigo_con_multiples_funciones_behavior_lanza_excepcion():
  unsafe_code = """
def behavior(player):
    player.correr((10, 10))
def behavior(player):
    player.saltar()
"""
  with pytest.raises(BehaviorValidationError):
      validate(unsafe_code) 

