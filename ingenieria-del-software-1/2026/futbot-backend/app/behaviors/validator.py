import ast
import multiprocessing
from app.schemas.coord import Coord
from app.behaviors.loader import BUILTINS_RESTRINGIDOS

TIMEOUT_SECONDS = 5
ALLOWED_PLAYER_METHODS = {
    "encontrar_pelota",
    "encontrar_aliado",
    "encontrar_enemigo",
    "encontrar_arco_aliado",
    "encontrar_arco_enemigo",
    "encontrar_mis_coordenadas",
    "tengo_pelota",
    "club_tiene_pelota",
    "pasar",
    "patear_pelota",
    "correr",
}
FORBIDDEN_NAMES = {
    "__builtins__",
    "__import__",
    "eval",
    "exec",
    "open",
    "compile",
    "input",
}
FORBIDDEN_FUNCTIONS = {
             'exec', 'eval', 'open', 'compile', 
             'input','__import__', 'getattr', 
             'setattr', 'delattr', 'globals', 
             'locals', 'vars', 'dir'
            }

# Objeto simulado para probar la función `behavior` sin necesidad de un jugador real.
class FakePlayer:
   def encontrar_pelota(self):
       return Coord(x=0, y=0)
   def encontrar_aliado(self):
       return Coord(x=0, y=0)
   def encontrar_enemigo(self):
       return Coord(x=0, y=0)
   def encontrar_arco_aliado(self):
       return Coord(x=0, y=0)
   def encontrar_arco_enemigo(self):
       return Coord(x=0, y=0)
   def encontrar_mis_coordenadas(self):
       return Coord(x=0, y=0)
   def tengo_pelota(self):
       return False
   def club_tiene_pelota(self):
       return False
   def pasar(self, objetivo):
       pass
   def patear_pelota(self, objetivo):
       pass
   def correr(self, objetivo):
       pass
    
# Excepciones personalizadas para errores de validación de comportamientos
class BehaviorValidationError(Exception):
    pass
class BehaviorSyntaxError(BehaviorValidationError):
    pass
class BehaviorSecurityError(BehaviorValidationError):
    pass
class BehaviorTimeoutError(BehaviorValidationError):
    pass

class BehaviorValidator(ast.NodeVisitor):
    """
    Clase que valida el código de un comportamiento personalizado.
    """
    def __init__(self):
        self.behavior_functions = 0
    
    def visit_Import(self, node):
      raise BehaviorSecurityError(f"Importaciones no permitidas: {ast.dump(node)}")
  
    def visit_ImportFrom(self, node):
        raise BehaviorSecurityError(f"Importaciones desde módulos no permitidas: {ast.dump(node)}")

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
          if node.func.id in FORBIDDEN_FUNCTIONS:
            raise BehaviorSecurityError(f"Llamada a función no permitida: {node.func.id}")
        elif isinstance(node.func, ast.Attribute):
            if  (
                isinstance(node.func.value, ast.Name) 
                and node.func.value.id == 'player'
                and node.func.attr not in ALLOWED_PLAYER_METHODS
            ):
                raise BehaviorSecurityError(f"Llamada a método de jugador no permitido: {node.func.attr}")
        
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == '__builtins__':
            raise BehaviorSecurityError(f"Acceso a __builtins__ no permitido: {ast.dump(node)}")
        if node.attr.startswith('__') or node.attr.startswith('_'):
            raise BehaviorSecurityError(f"Acceso a atributos privados no permitido: {node.attr}") 
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in FORBIDDEN_NAMES:
            raise BehaviorSecurityError(f"Uso de palabra reservada no permitido: {node.id}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name == "behavior":
            self.behavior_functions += 1
            if self.behavior_functions > 1:
              raise BehaviorValidationError("Solo se permite una función 'behavior' en el código.")
            if len(node.args.args) != 1:
                raise BehaviorValidationError("La función 'behavior' debe aceptar exactamente un argumento (el jugador).")
        self.generic_visit(node)


def _execute_code(code: str):
  '''Ejecuta el código en un proceso separado para limitar el tiempo de ejecución
  '''
  namespace = {"__builtins__": dict(BUILTINS_RESTRINGIDOS)}
  try: 
     exec(code, namespace)
     behavior_func = namespace.get("behavior")
     if not callable(behavior_func):
         raise BehaviorValidationError("El código del comportamiento no define una función 'behavior' válida.")
     player = FakePlayer()
     behavior_func(player)
  except Exception as e:
    raise BehaviorValidationError(f"Error durante la ejecución del código: {e}")

def validate(code: str):
  try:
      tree = ast.parse(code)
      validator = BehaviorValidator()
      validator.visit(tree)
      if validator.behavior_functions == 0:
        raise BehaviorValidationError("El código del comportamiento debe definir una función 'behavior'")

  except SyntaxError as e:
      raise BehaviorSyntaxError(f"Error de sintaxis en el código: {e}") 
  # Ejecutar el código en un proceso separado para limitar el tiempo de ejecución
  process = multiprocessing.Process(target=_execute_code, args=(code,))
  process.start()

  process.join(timeout=TIMEOUT_SECONDS)

  if process.is_alive():
    process.terminate()
    process.join()
    raise BehaviorTimeoutError("El código del comportamiento tardó demasiado en ejecutarse y fue terminado.")

  if process.exitcode != 0: # El proceso terminó con un error
    raise BehaviorValidationError("El código del comportamiento produjo un error durante la ejecución.")
