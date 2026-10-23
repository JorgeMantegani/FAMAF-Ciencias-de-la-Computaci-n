# **ALCANCE DEL PROYECTO**

El objetivo principal del proyecto es desarrollar un juego multijugador de fútbol web en donde los usuarios pueden crear sus clubes y ser identificados como tal, crear jugadores (y sus comportamientos), ligas para jugar entre clubes e inclusive participar en amistosos y ser espectador en partidos.
Lo distintivo de este juego, es que los futbolistas en cancha no son controlados manualmente por un usuario por teclado o mouse, en su lugar, los usuarios deben escribir código python para que los futbolistas en cancha se manejen de manera autónoma.
Habrá un sistema de ranking global y un fixture por liga. Las ligas pueden ser tanto públicas como privadas pero estas últimas no contarán para el puntaje global, tampoco cuentan los partidos amistosos.
La visualización de los encuentros se realiza en vivo y en tiempo real sobre una interfaz gráfica en 2D.

El sistema incluirá un buscador de liga con sus nombres y un buscador de partidos amistosos por código de sala amistosa, por lo cual no hay lista de amigos.
Una vez que la liga haya sido creada, la cantidad de usuarios mínima/máxima (definidas por el club creador de la liga) sea alcanzada, el creador de la sala podrá iniciar la liga, denegando la salida de la misma a los demás clubes participantes. En caso de que un club no quiera estar presente, simplemente puede no interactuar con el juego manteniendo los últimos cambios por defecto o que haya llegado a configurar al momento de unirse. Al finalizar un partido se mostrarán los resultados del mismo, y al finalizar una liga se mostrará el fixture de la misma, tras esto la sala se cierra y se deberá crear una nueva para poder jugar nuevamente. 


En cuanto a las mecánicas de juego:
- Todo usuario deberá tener una cuenta creada para poder jugar y la creación de sus jugadores requerirá distribuir exactamente 300 puntos entre los atributos PACSS, los cuales son power (fuerza de pateo), agility (tiempo para volver a patear), control (distancia para el control con la pelota), speed (velocidad y aceleración) y strength (imposición a los choques).
- Las ligas requieren de un mínimo de 3 clubes y pueden tener un máximo de 30, al momento de crearla se le pedirá contraseña al creador y si éste deja el campo vacío será una liga pública.
- Al entrar a una liga o partido deberá seleccionar 6 jugadores (3 titulares y 3 suplentes) a los cuales les tendrá que asignar un comportamiento programado previamente en código Python, mediante un archivo de extensión .py.
- Una vez creada la liga y que todos sus cupos hayan sido llenados, el creador podrá dar inicio.
- Los partidos se elegirán de forma aleatoria y se jugará una cantidad de partidos que se asegure que todos jueguen contra todos y se puede jugar un máximo de una vez contra cada rival.
- El partido estará separado en 4 tiempos (un medio tiempo y dos pausas de hidratación en cada mitad del medio tiempo).
- Al empezar el partido el usuario debe elegir la posición para cada uno de sus jugadores.
- Durante el partido el usuario puede hacer cambios de jugadores que impactaran en las pausas del partido.
- Se puede cambiar el comportamiento asignado a cada jugador lo cual tiene un impacto en el próximo tick.
- El sistema se construirá obligatoriamente bajo una arquitectura con backend en FastAPI y frontend en React, respetando la prohibición estricta de utilizar técnicas de polling para la comunicación cliente-servidor.

Que NO incluirá el proyecto:
- No hay lista de amigos.
- No se incluirá un editor de código IDE python.
- No habrá animaciones 3D.
- No hay puntuación para ranking en salas Amistosas ni Ligas Privadas.
