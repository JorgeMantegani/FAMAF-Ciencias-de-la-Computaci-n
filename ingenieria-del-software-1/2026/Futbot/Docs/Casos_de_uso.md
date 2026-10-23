# **CASOS DE USO**


## LISTADO DE CASOS POR MODULO:
### Autenticación y Perfil
1. Crear usuario
2. Login
3. Cerrar sesión
4. Editar avatar
### Gestión de Club
5. Crear Jugador
6. Eliminar Jugador
7. Ver listado de jugadores
8. Crear comportamiento
9. Consultar ejemplos de comportamiento pre programados
10. Editar comportamiento
11. Eliminar comportamiento
12. Consultar lista de comportamientos creados
### Matchmaking (Amistosos y Torneos)
13. Crear sala amistoso
14. Unirse a amistoso
15. Abandonar sala amistos 
16. Eliminar sala amistoso
17. Crear Liga pública
18. Crear Liga privada
19. Ver listado de Ligas públicas 
20. Ver listado de Ligas activas 
21. Unirse a Liga pública
22. Unirse a Liga privada 
23. Cancelar liga (solo creador, antes de iniciar)
24. Abandonar liga (solo participante, antes de iniciar)
25. iniciar liga
26. Consultar información de una Liga
27. Consultar fixture
### Partido
28. Ingresar formación de jugadores titulares
29. Editar formación
30. Iniciar partido
31. Programar sustitución
32. Modificar sustitución
33. Cambiar comportamiento durante el partido
34. Ver partido como espectador 
### Ranking
35. Consultar ranking global 

## CASOS DE USO ESPECIFICADOS:


- **_Crear_ _usuario_:**  
    Actor primario: Actor externo  
    Precondiciones: -  
    Escenario exitoso principal:  
    1. Actor primario: Ingresa datos (email, username, contraseña, nombre del club, avatar) en el formulario de registro.  
    2. Sistema: Valida datos, crea usuario, genera token de sesión e informa que el registro fue exitoso mediante un pop-up.

    Escenario excepcional:
    
    - 2.A Sistema: Detecta email en uso por otro usuario.  
    Pide al actor que ingrese otro email mediante un pop-up y el caso de uso retorna al paso 1.

- **_Login_**:  
    Actor primario: Actor externo  
    Precondiciones: Actor primario registrado en el sistema  
    Escenario exitoso principal:  
    1. Actor primario: Ingresa sus datos (email y contraseña) al formulario de ingreso.
    2. Sistema: Valida datos, genera token de sesión y permite el acceso a página principal.

    Escenario excepcional:  
    
    - 2.A Sistema: Detecta email o contraseña incorrecta  
    Pide al actor que ingrese datos correctos y el caso de uso retorna al paso 1.

- **_Cerrar_ _sesión_**:  
    Actor primario: Usuario logueado.  
    Precondiciones:-  
    Escenario exitoso principal:  
    1. Actor primario: Pide al sistema cerrar su sesión haciendo click en el botón “cerrar sesión”  
    2. Sistema: El sistema cierra la sesión e invalida el token

- **_Editar_ _avatar_ _del_ _club_**:   
    Actor primario: Usuario logueado  
    Precondiciones:-  
    Escenario exitoso principal:  
    1. Actor primario: entra a su perfil y toca su avatar  
    2. Sistema: cuando el cursor pasa por encima muestra un lápiz y le presenta la opción de ver el avatar o modificarlo  
    3. Actor primario: selecciona la opción de modificar el avatar y sube la nueva foto.


- **_Crear_ _Jugador_**:  
    Actor primario: Usuario Logueado  
    Precondiciones: -  
    Escenario exitoso principal:  
    1. Actor primario: Hace click en el botón “Crear Jugador”.  
    2. Sistema:  Redirigido al actor a otra ventana/página  
    3. Actor primario: ingresa los datos para el jugador (nombre, y los atributos PACSS) y elige la opción de guardar jugador haciendo click en el botón “Guardar Jugador”.  
    4. Sistema: Valida datos (nombre, Atributos PACSS), crea el jugador e informa que el jugador está listo para usarse mediante un pop-up de confirmación.  
    
    Escenario excepcional:  

    - 4.A Sistema: detecta atributos mayores a 100 o menores a 20 o que la suma de los cinco atributos no es exactamente 300  
    Pide al actor que ingrese valores válidos mediante un mensaje pop-up y el caso de uso retorna al paso 1.

- **_Eliminar_ _Jugador_**:  
    Actor primario: Usuario logueado  
    Precondiciones:  Jugador a eliminar existente y tener abierto el listado de jugadores  
    Escenario exitoso principal:  
    1. Actor primario: Selecciona el jugador a eliminar y hace click en la X roja junto al jugador.  
    2. Sistema: Valida que el jugador no esté participando en ligas ni partidos actuales, lo elimina e informa que el jugador ya no existe mediante un pop-up.

    Escenario excepcional:   

    - 2.A Sistema: Detecta que el jugador está participando en una liga o partido actual.  
    Impide su eliminación, le pide al actor seleccionar otro jugador mediante un pop-up.

- **_Ver_ _Listado_ _de_ _Jugadores_**:  
    Actor primario: Usuario logueado  
    Precondiciones: -  
    Escenario exitoso principal:  
    1. Actor primario: toca botón “plantel”   
    2. Sistema: Redirige al actor a la página de plantel y muestra todos los jugadores con sus atributos.

- **_Crear_ _comportamiento_**:  
    Actor primario: Usuario logueado  
    Precondiciones: -  
    Escenario exitoso principal:  
    1. Actor primario: Hace clic en el botón “Crear Comportamiento”  
    2. Sistema: Despliega un formulario solicitando ingresar un nombre del comportamiento y cargar el archivo de código.  
    3. Actor primario: Ingresa el nombre del comportamiento en el campo correspondiente y carga el archivo .py correspondiente con el código en python, respetando la especificación provista (API de primitivas).  
    4. Sistema: Verifica y registra tanto el nombre como el código del comportamiento en la base de datos, luego notifica al club que el comportamiento fue creado con éxito mediante un pop-up.  

    Escenarios excepcionales:  

    - 4.A Sistema: Detecta que el nombre ya existe en esta cuenta y solicita al actor primario un nuevo nombre para el comportamiento mediante un pop-up.  

    - 4.B Sistema: Detecta que el código tiene funciones no permitidas o no son utilizadas correctamente y solicita al actor primario la revisión y reenvío del código mediante un pop-up.


- **_Consultar_ _ejemplos_ _de_ _comportamiento_ _pre_ _programados_**:  
    Actor primario: Usuario logueado  
    Precondiciones:-  
    Escenario exitoso principal:  
    1. Actor primario: Usuario accede a la sección de comportamientos y consulta los comportamientos preprogramados.  
    2. Sistema: Muestra los comportamientos preprogramados disponibles a través de un pop-up.

- **_Editar_ _comportamiento_**:  
    Actor primario: Usuario logueado  
    Precondiciones: haber creado el comportamiento, tener abierto el listado de comportamientos y que no este asignado a un jugador.  
    Escenario exitoso principal:  
    1. Actor primario: elige qué comportamiento quiere editar dandole un click.  
    2. Sistema: muestra un pop-up donde el actor debe cargar el archivo con el nuevo código de comportamiento.  
    3. Actor primario: carga el archivo  
    4. Sistema: valida el comportamiento, guarda la actualización del mismo e informa que ya puede usarse.  

    Escenario excepcional:  

    - 4.A Sistema: el archivo cargado no es válido, el sistema pide que ingrese un archivo nuevamente  

    - 4.B Sistema: detecta código invalido en el nuevo comportamiento.  
    El sistema pide al actor que corrija el código del comportamiento y cargue el archivo nuevamente.


- **_Eliminar_ _Comportamiento_**:  
    Actor primario: Usuario logueado  
    Precondiciones: Comportamiento a eliminar existente, tener abierto el listado de comportamientos y que no este asignado a un jugador  
    Escenario exitoso principal:  
    1. Actor primario: Selecciona un comportamiento a eliminar del listado mediante un click.  
    2. Sistema: Muestra el comportamiento con un pop-up y una equis roja al lado  
    3. Actor primario: Selecciona la equis roja.  
    4. Sistema: Verifica mediante un mensaje en un pop-up la intención de eliminar el comportamiento.  
    5. Actor primario: confirma la decisión dándole click a “confirmar”  
    6. Sistema: Elimina el código y el nombre del comportamiento de la base de datos,lo elimina de la lista de comportamientos de la cuenta y notifica al usuario que el comportamiento fue eliminado con éxito.  

    Escenario excepcional:  

    - 5.A Actor primario: niega la decisión y el sistema vuelve al estado inicial 

- **_Consultar_ _lista_ _de_ _comportamientos_ _creados_**:  
    Actor primario: Usuario logueado  
    Precondiciones: -  
    Escenario exitoso principal:  
    1. Actor primario: entra a la sección comportamientos mediante un click en el botón “comportamientos”.  
    2. Sistema: le muestra los diferentes comportamientos creados por el Actor mediante un pop-up


- **_Crear_ _sala_ _amistoso_**:   
    Actor primario: Usuario logueado  
    Precondiciones:  El club del actor primario tiene al menos 6 jugadores creados.  
    Escenario exitoso principal:   
    1. Actor primario: selecciona crear amistoso mediante un botón   
    2. Sistema: instancia la sala, genera y muestra el código de la sala, y  pide al actor que ingrese 3 jugadores titulares y 3 jugadores suplentes mediante un pop-up con un listado de los jugadores y les asigne comportamiento.  
    3. Actor primario: selecciona los 3 jugadores titulares y los 3 jugadores suplentes haciendo click en jugadores del listado y les asigna un comportamiento.  
    4. Sistema: valida que los jugadores sean seleccionables.  

    Escenario excepcional:  

    - 4.A Sistema: detecta jugadores no seleccionables y pide que los ingrese nuevamente.


- **_Unirse_ _a_ _amistoso_**:   
    Actor primario: Usuario logueado  
    Precondiciones: El club del actor primario tiene al menos 6 jugadores creados, que la sala no esté llena ni iniciada.  
    Casos de uso relacionados:  

    - Caso de uso # 30: Iniciar partido  

    Escenario exitoso principal:   
    1. Actor primario: Ingresa el código de sala amistosa a la que desea unirse en el campo de “búsqueda de sala”  
    2. Sistema: valida el código de sala, da acceso al actor primario y le pide a este que ingrese 6 jugadores mediante un pop-up y les asigne comportamiento.  
    3. Actor primario: selecciona los 6 jugadores de su listado de jugadores, haciendo click en cada uno y les asigna comportamiento.  
    4. Sistema: valida que los jugadores sean seleccionables y ejecuta el Caso de uso # 30: Iniciar partido  

    Escenario excepcional:  

    - 2.A Sistema: detecta que el código es invalido, pide que se ingrese un nuevo código y notifica al usuario mediante un pop-up.  

    - 4.A Sistema: detecta jugadores no seleccionables y pide que los ingrese nuevamente mediante un pop-up.  

- **_Abandonar_ _sala_ _amistoso_**:  
    Actor primario: Usuario logueado  
    Precondiciones: Actor primario debe estar en la sala amistoso, no ser el creador de la sala y que el partido no esté iniciado.  
    Escenario exitoso Principal:  
    1. Actor primario: pulsa el botón de “abandono de sala”  
    2. Sistema: pide la confirmación de abandono de sala mediante un pop-up.  
    3. Actor primario: confirma el abandono de la sala pulsando el botón de confirmación.  
    4. Sistema: saca al actor primario de la sala, lo retorna al homepage y habilita nuevamente la sala para que se pueda unir otro usuario.  

    Escenario alternativo:   
	
    - 3.A Actor primario: cancela el abandono de la sala haciendo click en el botón de cancelación.  

- **_Eliminar_ _sala_ _amistoso_**:  
    Actor primario: Usuario logueado  
    Precondiciones: Actor primario debe haber creado la sala amistosa y esta no estar iniciada  
    Escenario exitoso Principal:  
    1. Actor primario: solicita borrar la sala amistosa presionando el botón “eliminar sala”.  
    2. Sistema: pide confirmación para borrar la sala amistosa con un pop-up.  
    3. Actor primario: confirma la eliminación de la sala amistosa presionando el botón “confirmar”.  
    4. Sistema: remueve de la sala a ambos clubes, los retorna al homepage, borra la sala amistosa y notifica al club creador la eliminación de la sala mediante un pop-up.  

    Escenario alternativo:  

    - 3.A Actor primario: el actor no confirmó la eliminación de la sala, por lo que la sala no se elimina.

- **_Crear_ _Liga_ _pública_**:  
    Actor primario: Usuario logueado   
    Precondiciones: Actor principal debe tener 6 jugadores en su plantel  
    Escenario exitoso principal:   
    1. Actor primario: solicita al sistema la opción de crear una liga nueva pulsando el botón “Crear Liga”.  
    2. Sistema: pide al actor ingresar datos de liga (nombre de liga, mínimo y máximo número de clubes y duración de los partidos) a través de un formulario pop-up.  
    3. Actor primario: ingresa datos de liga.  
    4. Sistema: Valida que los parámetros ingresados sean los correctos y pide al actor que ingrese 3 jugadores titulares y 3 jugadores suplentes para competir en la liga a través de un pop-up y les asigne comportamiento.  
    5. Actor primario: selecciona los 3 titulares y 3 suplentes de su plantilla de jugadores y les asigna comportamiento.  
    6. Sistema: valida la selección del plantel elegido e inscribe automáticamente al club organizador en la nueva liga, confirmando la creación de la misma y le notifica al actor que fue unido a la misma.  

    Escenario excepcional:  

    - 4.A Sistema: detecta que los datos ingresados son erróneos( nombre de liga ya existente) y le pide al actor que reingrese los datos mediante un pop-up.  

    - 6.A Sistema: detecta jugadores no válidos y avisa al actor primario para que reingrese nuevos jugadores mediante un pop-up.


- **_Crear_ _Liga_ _Privada_**:  
    Actor primario: Usuario logueado  
    Precondiciones: Actor principal debe tener 6 jugadores en su plantel.  
    Escenario exitoso principal:  
    1. Actor primario: solicita al sistema la creación de una liga privada pulsando el botón “Crear Liga privada”.  
    2. Sistema: pide al actor ingresar datos de liga (N° mínimo y máximo de usuarios, nombre de liga y duración de los partidos) a través de un formulario pop-up.  
    3. Actor primario: Ingresa los datos de liga en el formulario.  
    4. Sistema: Valida los parámetros ingresados, pide al actor principal ingresar 3 jugadores titulares y 3 jugadores suplentes a través de un pop-up  y les asigne comportamiento.  
    5. Actor primario: selecciona 3 titulares y 3 suplentes de su plantilla de jugadores y les asigna comportamiento.  
    6. Sistema: valida la selección de jugadores e inscribe al club organizador en la nueva liga, genera el código de sala, confirma la creación de la liga e informa el código de sala mediante un pop-up y le notifica al actor que fue unido a la misma.  

    Escenario excepcional:  

    - 4.A Sistema: detecta que los datos ingresados son erróneos y le pide al actor primario que reingrese los datos mediante un pop-up. 
      
    - 6.A Sistema: detecta jugadores no válidos y avisa al actor primario que ingrese nuevos jugadores mediante un pop-up.




- **_Ver_ _listado_ _de_ _ligas_ _públicas_**:   
    Actor primario: Usuario logueado  
    Precondiciones: -  
    Escenario exitoso principal:   
    1. Actor primario: selecciona la opción “ver ligas públicas” con un click.  
    2. Sistema: imprime mediante un pop-up las ligas públicas existentes.


- **_Ver_ _Listado_ _de_ _Ligas_ _Activas_**:    
    Actor primario: Usuario logueado  
    Precondiciones: -  
    Escenario exitoso principal:    
    1. Actor primario:  entra al perfil con un click.   
    2. Sistema: Muestra en el perfil diferentes categorías entre la que se encuentra “ligas activas donde muestra todas las ligas en las que está participando el usuario


- **_Unirse_ _a_ _Liga_ _pública_**:    
    Actor primario: Usuario logueado    
    Precondiciones: Actor primario con 6 jugadores en su plantel    
    Casos de uso relacionados:  

    - Caso de uso #19: Ver listado de ligas públicas.   

    Escenario exitoso principal:     
    1. Actor primario: el actor ejecuta el Caso de uso #19: Ver listado de ligas públicas y selecciona a cuál quiere unirse mediante un click en la misma.   
    2. Sistema: muestra mediante un pop-up los jugadores del actor para que el mismo seleccione sus jugadores titulares y suplentes para la liga  y les asigne comportamiento.  
    3. Actor primario: elige a sus 3 jugadores titulares y sus 3 jugadores suplentes seleccionándolos en el listado, y asigna sus comportamientos.  
    4. Sistema: Valida que los jugadores sean seleccionables, une al club a la liga y le notifica al actor que fue unido a la misma.    

    Escenario excepcional:      

    - 4.A Sistema: detecta jugadores no seleccionables, avisa al usuario y le pide que ingrese los jugadores nuevamente mediante un pop-up.

- **_Unirse_ _a_ _Liga_ _Privada_**:    
    Actor primario: Usuario logueado    
    Precondición: Actor primario posee al menos 6 jugadores en su plantel.      
    Escenario exitoso principal:    
    1. Actor primario: Ingresa el código de sala en el campo “búsqueda de sala privada” de la sección de búsqueda de ligas y hace click en el botón “buscar”.   
    2. Sistema: Valida el código de sala, le pide ingresar 3 jugadores titulares y 3 jugadores suplentes mediante un pop-up, así como asignar comportamiento a los 6 jugadores  y les asigne comportamiento.    
    3. Actor primario: Selecciona los jugadores pedidos de su listado de jugadores haciendo click en ellos. 
    4. Sistema: Valida la selección de jugadores, une al actor a la liga y le notifica al actor que fue unido a la misma.   

    Escenario excepcional:  

    - 2.A Sistema: detecta un código de sala invalido y le pide al actor principal ingresar un nuevo código de sala mediante un pop-up.  

    - 4.A Sistema: detecta jugadores no seleccionables, avisa al usuario y le pide que ingrese los jugadores nuevamente mediante un pop-up.


- **_Cancelar_ _liga_**:    
    Actor primario: Usuario logueado    
    Precondiciones: Actor primario es el creador de la liga seleccionada y la liga seleccionada aún no fue iniciada.    
    Escenario exitoso principal:     
    1. Actor primario: solicita al sistema cancelar liga seleccionada a través del botón “cancelar liga”    
    2. Sistema: solicita al club creador una confirmación explícita para proceder con la cancelación a través de un pop-up. 
    3. Actor primario: confirma la cancelación de la liga   
    4. Sistema: elimina de forma definitiva el registro de la liga, anula todas las inscripciones vigentes de los clubes que se habían unido y notifica la baja del torneo a todos los participantes e informa al actor que la liga fue cancelada con éxito.

    Escenario alternativo:

    - 3.A Actor primario: Revierte la cancelación de la liga pulsando el botón de negación.

    - 4.A Sistema: Devuelve al jugador a la vista anterior manteniendo el estado de la liga sin cambios. 



- **_Abandonar_ _liga_**:   
    Actor primario: Usuario logueado     
    Precondiciones: Actor primario está inscripto en la liga seleccionada, la liga seleccionada aún no fue iniciada y el actor primario no es creador de la liga.    
    Escenario exitoso principal:     
    1. Actor primario: selecciona el botón “abandonar liga” de la la liga correspondiente de su lista de torneos activos    
    2. Sistema: solicita al club creador una confirmación explícita para proceder con la abandonar liga a través de un pop-up.  
    3. Actor primario: confirma la acción de abandonar liga     
    4. Sistema: elimina definitivamente la inscripción del club participante, liberando el cupo de la liga, desvinculando la selección de sus 6 jugadores para este torneo e informa al actor que la liga se abandonó con éxito.         
    
    Escenario alternativo:      

    - 3.A Actor primario: Revierte la cancelación de la liga pulsando el botón de negación.

    - 4.A Sistema: Devuelve al jugador a la vista anterior manteniendo el estado de la liga sin cambios. 




- **_Iniciar_ _liga_**: 
    Actor primario: Usuario logueado    
    Precondiciones: Actor primario es el creador de la liga, la liga aún no fue iniciada y tiene mínimo 3 clubes participantes  
    Escenario exitoso principal:     
    1. Actor primario: selecciona el botón “iniciar liga”.  
    2. Sistema: bloquea de manera definitiva la posibilidad de abandonar la liga para todos los clubes participantes, y la posibilidad de cancelar la liga para el creador, genera automáticamente el fixture de la competencia bajo el nombre de “todos contra todos”, registra el estado de la liga como iniciada, informa al club creador la confirmación de inicio exitoso y le presenta el fixture generado para el torneo con un pop-up, y permite el inicio de los partidos en un orden. 

- **_Consultar_ _información_ _de_ _una_ _liga_**:   
    Actor primario: Usuario logueado        
    Precondiciones: -       
    Casos de usos relacionados:     

    - Caso de uso #19: Ver listado de ligas públicas.       

    Escenario exitoso principal:    
    1. Actor primario: Ejecuta - Caso de uso #19: Ver listado de ligas públicas, selecciona la liga de interés y hace click en el botón “Información”.      
    2. Sistema: Muestra tabla de puntaje y listado de clubes participantes mediante un pop-up.


- **_Consultar_ _fixture_ _de_ _liga_**:    
    Actor primario: Usuario logueado         
    Precondiciones: Actor primario pertenece a una liga y la liga ya fue iniciada       
    Escenario exitoso principal:        
    1. Actor primario: selecciona el botón “consultar fixture” de la liga correspondiente.       
    2. Sistema: muestra al actor primario un pop-up de la lista completa del cronograma de partidos (con los resultados si el encuentro fue finalizado).



- **_Ingresar_ _formación_ _de_ _jugadores_ _titulares_**:      
    Actor primario: Usuario logueado        
    Precondiciones: el partido ha sido inicializado por el servidor y el club se encuentra en pre-partido obligatorio de 30 segs        
    Escenario exitoso principal:         
    1. Actor primario: selecciona la opción de ingresar formación  mediante un click en el botón “Ingresar formación”.      
    2. Sistema: le muestra un pop-up con información de las formaciones donde el actor debe ingresar su formación.      
    3. Actor primario: ingresa la formación de los titulares.       
    4. Sistema: valida la formación.    

    Escenario Excepcional:

	- 4.A Sistema: La formación no es válida, el sistema pide que se ingrese una formación valida.


- **_Editar_ _formación_**: 
    Actor primario: Usuario logueado    
    Precondiciones: el actor primario se encuentra jugando un partido y en una pausa del mismo.     
    Escenario exitoso principal:    
    1. Actor primario: selecciona la opción de cambiar formación  mediante un click en el botón “cambiar formación”.    
    2. Sistema: le muestra un pop-up con información de las formaciones donde el actor debe ingresar la nueva formación.        
    3. Actor primario: ingresa la nueva formación de los titulares en el pop-up.    
    4. Sistema: valida la formación e informa al actor primario mediante un pop-up.     

    Escenario Excepcional:  

    - 4.A Sistema: La formación no es válida, el sistema pide que se reingrese la formación mediante un pop-up.


- **_Iniciar_ _partido_**:  
    Actor primario: Usuario logueado    
    Precondiciones: Actor primario ingresó exitosamente a una sala y esta cumple el mínimo de usuarios para su inicio.  
    Casos de uso relacionados:      

    - Caso de uso # 28: Ingresar formación de jugadores titulares  

    Escenario exitoso principal:    
    1. Actor primario: selecciona la opción “Iniciar partido” mediante un click, ejecuta el Caso de uso # 28: Ingresar formación de jugadores titulares.        
    2. Sistema: Espera 30 segundos, valida que los clubes participantes tengan su formación y comportamientos definidos y da inicio al partido, mostrando una simulación en pantalla.   

    Escenario excepcional:  

    - 2.A Sistema: detecta que pasados los 30 segundos el actor no definió la formación ni comportamientos. El sistema por medio del “Manager Automático” sortea y asigna aleatoriamente la formación y los comportamientos.Da inicio al partido, mostrando una simulación en pantalla. 

    - 2.B Sistema: detecta que el actor principal abandonó el partido. El partido continúa jugándose de forma automática utilizando la formación y comportamientos por defecto del club ausente, manteniendo la transmisión de la simulación en pantalla para el oponente y espectadores.



- **_Programar_ _sustitución_**:    
    Actor primario: Usuario logueado    
    Precondiciones: el actor primario se encuentra jugando un partido y existe una próxima pausa.    
    Escenario exitoso principal:     
    1. Actor primario: selecciona el botón “programar sustitución”   
    2. Sistema: abre un pop-up para que el actor ingrese un jugador en cancha a quiere sustituir y un jugador suplente para ingresar.   
    3. Actor primario: ingresa los dos jugadores que quiere sustituir y suplantar correspondientes. 
    4. Sistema: valida los estados actuales de ambos jugadores, confirma que el partido tenga pausas próximas y que el actor no tenga otra sustitución programada para la próxima pausa. Guarda la sustitución para ejecutarla en la próxima pausa disponible e informa al actor mediante un pop-up.

    Escenario excepcional:  

	- 4.A Sistema: detecta que el partido ya no tiene pausas  
    Informa mediante un pop-up al actor que el partido no tiene pausas y ya no pueden realizarse cambios, rechaza el cambio y el caso de uso finaliza.  

    - 4.B Sistema: detecta que el actor ya tiene un cambio programado para la siguiente pausa.  
    Informa mediante un pop-up al actor que ya se programó una sustitución y ya no pueden realizarse otra antes de la siguiente pausa, rechaza la sustitución y el caso de uso finaliza. 


- **_Modificar_ _sustitución_**:    
    Actor primario: Usuario logueado    
    Precondiciones: actor primario está participando en un partido en curso y tiene una sustitución programada.      
    Escenario exitoso principal:     
    1. Actor primario: selecciona la edición de la sustitución programada, haciendo click en la opción “editar sustitución”.    
    2. Sistema: valida que la sustitución no haya sido ejecutada y le pide al actor que ingrese un jugador en cancha a quien sustituir y un jugador suplente para ingresar mediante un pop-up.  
    3. Actor primario: Selecciona los jugadores pedidos del pop-up. 
    4. Sistema: Valida los estados actuales de ambos jugadores, guarda las modificaciones de la sustitución para ejecutarla en la próxima pausa y le confirma al actor principal mediante un pop-up.

    Escenario excepcional:

	- 2.A Sistema: detecta que la sustitución ya fue ejecutada, informa al actor que la sustitución ya se hizo y ya no puede modificarse mediante un pop-up.

    - 4.A Sistema: detecta que la sustitución es inválida, rechaza las modificaciones e informa al actor primario mediante un pop-up. 


- **_Cambiar_ _comportamiento_ _durante_ _el_ _partido_**:  
    Actor primario: Usuario logueado    
    Precondiciones: el actor primario debe estar participando en un partido en curso  
    Escenario exitoso principal:     
    1. Actor primario: selecciona un jugador en cancha al cual le quiere cambiar el comportamiento  
    2. Sistema: muestra la lista ,mediante un pop-up, de comportamientos ya creados por el actor primario.   
    3. Actor primario: selecciona el nuevo comportamiento de la lista y toca el botón de confirmación   
    4. Sistema: valida que el partido siga en curso, aplica el comportamiento al jugador en el siguiente tick y confirma la actualización en pantalla. 

    Escenario excepcional:

	- 4.A Sistema: detecta que el partido acaba de finalizar.   
    Informa al actor que el partido terminó, rechaza el cambio y el caso de uso finaliza. 


- **_Ver_ _partido_ _como_ _espectador_**:  
    Actor primario: Usuario logueado    
    Precondiciones: -    
    Casos de uso relacionados:  

    - Caso de uso #19: Ver listado de ligas públicas    

    Escenario exitoso principal:    
    1. Actor primario: ejecuta el caso de uso #19 y selecciona de la lista de ligas públicas cuál quiere ver.    
    2. Sistema: valida que la liga siga en juego y con partidos activos. 

    Escenario excepcional:

    - 2.A Sistema: detecta que la liga ya terminó.  
    Informa al actor que la liga ya no está disponible, le muestra al actor la tabla de posiciones de la liga y termina el caso de uso.



- **_Consultar_ _ranking_ _global_**:   
    Actor primario: Usuario logueado    
    Precondiciones: -   
    Escenario exitoso principal:    
    1. Actor primario: Toca el botón “ranking global”.   
    2. Sistema: El sistema ordena a los clubes por puntaje que se calcula basándose en los puntos sumados en las ligas que juegan, partidos amistosos y torneos ganados (no se contabilizan los puntos obtenidos en ligas privadas). Despliega un pop-up con los primeros 10 clubes del ranking y la posición del club del actor principal.
