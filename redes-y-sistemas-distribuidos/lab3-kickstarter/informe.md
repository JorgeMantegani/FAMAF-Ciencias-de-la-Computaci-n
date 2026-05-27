# INTEGRANTES GRUPO 26: 
- Peyretti Marcos
- Mantegani Jorge
- Luna Olariaga Valentin
- Ayala Garcia Luis Facundo

# Informe experimental - Parte 1

### RESUMEN:
<p>Se modela una red simple que pone incapie en la relacion de el tamaño de los paquetes, tasas de transmición y buffers limitados en sus nodos.<br>
Se busca estudiar el flujo de la red y como afectan sus componentes.<p>

### 1. ¿Qué diferencias observan entre el Caso 1 y el Caso 2?

- En el Caso 1 se observa una acumulación muy fuerte de paquetes en el buffer de recepción del nodo (`Network.nodeRx.rxBuffer`) y los paquetes empiezan a perderse en ese mismo buffer.
- En el Caso 2 se observa que la pérdida de paquetes ocurre en el buffer de la cola de la red (`Network.queue`), y la ocupación de la cola se mantiene al máximo mientras los paquetes se descartan.

En términos de métricas, el Caso 1 presenta un `bufferSize` alto en el receptor y drops en `nodeRx.rxBuffer`, mientras que el Caso 2 muestra drops en `Network.queue` y la cola de red es el recurso saturado.

### 2. ¿Cuál es la fuente limitante en cada caso?

- Caso 1: la fuente limitante es el receptor. El receptor no puede procesar o vaciar los paquetes tan rápido como el emisor los envía, por lo que su buffer de recepción se llena.
- Caso 2: la fuente limitante es la red (la cola compartida). El recurso de red se satura antes que el receptor, y por eso los paquetes se pierden en la cola de la red.

### 3. ¿En qué caso se observa un problema de control de flujo y en cuál uno de control de congestión?

- Caso 1 es un problema de control de flujo.
- Caso 2 es un problema de control de congestión.

### 4. ¿Qué evidencia experimental usan para sostener esa conclusión?

- Para el Caso 1:
  - La evidencia es que la métrica `bufferSize` en `Network.nodeRx.rxBuffer` crece hasta valores máximos muy altos.
  - Además, el archivo de pérdidas muestra que los paquetes se descartan en el receptor (`droppedPackets in Network.nodeRx.rxBuffer`).
  - Esto indica que el emisor está enviando más rápido de lo que el receptor puede aceptar, lo cual es el síntoma clásico del control de flujo.

- Para el Caso 2:
  - La evidencia es que las pérdidas aparecen en `Network.queue` y la cola de red se mantiene casi llena.
  - El `bufferSize` de la cola de la red se mantiene en niveles máximos mientras los paquetes se descartan en la cola.
  - Esto demuestra que el problema no es la capacidad del receptor sino el recurso de red compartido, por lo que es un problema de congestión.

## Figuras experimentales

| Caso | rxBuffer | txBuffer | Queue | dropPackets |
|----|----|----|----|----|
| 1 | ![](<graficos/parte1/graficos_caso3/bufferSize in Network.nodeRx.rxBuffer.png>) | ![](<graficos/parte1/graficos_caso3/bufferSize in Network.nodeTx.txBuffer.png>) | ![](<graficos/parte1/graficos_caso3/bufferSize in Network.queue.png>) | ![](<graficos/parte1/graficos_caso3/droppedPackets in Network.nodeRx.rxBuffer.png>) |
| 2 | ![](<graficos/parte1/graficos_caso4/bufferSize in Network.nodeRx.rxBuffer.png>) | ![](<graficos/parte1/graficos_caso4/bufferSize in Network.nodeTx.txBuffer.png>) | ![](<graficos/parte1/graficos_caso4/bufferSize in Network.queue.png>) | ![](<graficos/parte1/graficos_caso4/droppedPackets in Network.queue.png>) |



# Informe experimental - Parte 2
### RESUMEN:
<p>Se complejiza la red con la integración de un sistema de control por ventanas simple.<br>Buscamos estudiar la optimizacion del sistema y el funcionamiento practico del sistema de control.<p>

### 1. ¿Cómo implementaron rwnd, cwnd y effectiveWindow?

- Calculamos rwnd en NodeRx como: `rwnd = bufferSize - rxBuffer.size()`, esto significa, el tamaño impuesto en el caso a estudiar menos el tamaño actual del buffer del nodo.

- cwnd funciona como un limitador, tal que no se enviaran mensajes si estos superarian la ventana de congestión. cwnd será calculada en base a la informacion en los ACK's usando el metodo AIMD.

- effectiveWindow se calcula en cada intento de envio como: `effectiveWindow = min(cwnd, rwnd)` , funciona como un limitador activo de la capacidad de envio en el nodo de envio NodeTx.
### 2. ¿Qué información viaja en el feedback?

- Tipo de mensage, en el parametro "kind" (DATA, ACK, WINDOW_UPDATE).

- Receiver Window, el parametro "rwnd", indica el espacio disponible en el buffer del receptor

- Explicit Congestion Notification, en el parametro "ecn", indica una instancia de congestion.
### 3. ¿Qué condición usa el transmisor para enviar o esperar?

- Se calcula la posibilidad de envio en base a que el buffer no este vacio y que hayan menos paquetes en vuelo que la cantidad posible en la ventana efectiva. De esta forma, no iniciamos una secuencia de envio con un buffer vacio para evitar errores y no mandamos mas paquetes que los necesarios para evitar la perdida de paquetes.
### 4. ¿Cómo detectan congestión?

- Detectamos la congestion de dos formas, en el nodo receptor cuando se supera el tamaño del buffer notificamos congestion mandando una WINDOW_UPDATE con ecn. En los nodos Queue cuando el tamaño del buffer supera el 80%, marcamos ECN de forma explicita.
### 5. ¿Cómo cambia cwnd cuando hay congestión y cuando no la hay?

- Sin Congestion: aplicamos crecimiento aditivo, aumentando cwnd lentamente hasta alcanzar una ventan efectiva optima.

- Con Congestion: aplicamos reduccion multiplicativa, reaccionamos de forma proporcional, reduciendo cwnd a la mitad.
### 6. ¿El algoritmo funciona igual para el Caso 1 y el Caso 2? ¿Por qué?

- El problema en el caso 1 esta en un cuello de botella en el lado del receptor, el sistema responde disminuyendo rwnd y por ende la ventana efectiva para mitigar la perdida de paquetes, este ajuste se hace mediante los ACK's y la red permite una respuesta rapida.

- El problema en el caso 2 es un cuello en la red misma, se pierden paquetes por saturacion del buffer en la red, el sistema responde reduciendo cwnd y por ende la ventana efectiva para mitigar la perdida de paquetes, este ajuste se hace mediante notificaciones ECN, es efectivo pero lento ya que la restriccion esta en la velocidad de la red.
### 7. ¿Logra reducir o eliminar pérdidas?

- Este sistema logra reducir las perdidas pero no las elimina completamente, ya que es dependiente del tiempo de respuesta y puede tardar en adaptar la ventana efectiva en algunas configuraciones, en esencia busca un balance en la capacidad de los buffers tal que no haya perdidas por overflow, pero si las condiciones cambian, puede tardar mucho en adaptarse a la red.
### 8. ¿Qué costo tiene la solución? Por ejemplo: mayor demora, menor carga útil, oscilaciones, subutilización del enlace.
El sistema sufre de:
- Mayor demora: los paquetes deben esperar en el buffer a los ACK's
- Menor carga util: el encalce puede estar infraultilizado mientras cwnd sea pequeño, lo cual sucede a menudo ya que el escalado es marginal.
- Oscilaciones: se puede observar que cwnd tiene forma de "diente de sierra" dada la forma en que se calcula con cada envio, esto lleva a variaciones en la tasa de envio.
- Overhead: los ACK's consumen un ancho de banda estatico por cada paquete enviado, lo cual puede saturar el sistema si el ancho de banda disponible es pequeño.

### 9. ¿Qué limitaciones tiene su diseño y cómo podría mejorarse?
<p>El sistema actual presenta varias limitaciones:<p>

- No retransmision: si un paquete se pierde, no hay posibilidad de recuperarlo ya que no estamos utilizando numero de secuencia.
- No es posible estimar RTT: los ACK's no utilizan timestamp, con lo cual no podemos calcular cambios bruscos en la red.
- ECN como bool: actualmente solo sabemos que hay congestion y no cuan severa es.
- Escalado lento de cwnd: el escalado actual lineal, lo cual implica que el sistema tarda mucho en adaptarse a la capacidad de la red.

<p>Posibles soluciones:<p>

- Usar numeros de secuencia para retransmiciones en caso de perdida de paquetes.
- timestamp en los ACK's para un mayor control de la red y estimacion de RTT.
- Umbral ECN dinamico que se ajuste segun RTT y tasa de perdida de paquetes.
- Crecimiento exponencial de cwnd para una respuesta mas rapida al estado de la red.

## Figuras experimentales
| Parametro | Caso 1 | Caso 2 |
|----|----|----|
|txBufferOccupancy| ![](<graficos/parte2/graficos_caso3/txQueueOccupancy in Network.nodeTx.transport.png>) | ![](<graficos/parte2/graficos_caso4/txQueueOccupancy in Network.nodeTx.transport.png>) |
|rxBufferOccupancy| ![](<graficos/parte2/graficos_caso3/rxBufferOccupancy in Network.nodeRx.transport.png>) | ![](<graficos/parte2/graficos_caso4/rxBufferOccupancy in Network.nodeRx.transport.png>) |
|DroppedPackets| ![](<graficos/parte2/graficos_caso3/gi0,1 droppedPackets in Network.queue.png>) | ![](<graficos/parte2/graficos_caso4>) |
|rwnd|![](<graficos/parte2/graficos_caso3/rwnd in Network.nodeTx.transport.png>)|![](<graficos/parte2/graficos_caso4/rwnd in Network.nodeTx.transport.png>)|
|cwnd|![](<graficos/parte2/graficos_caso3/Line Chart 5.png>)|![](<graficos/parte2/graficos_caso4/Line Chart 5.png>)|
|effectiveWindow|![](<graficos/parte2/graficos_caso3/Line Chart 4.png>)|![](<graficos/parte2/graficos_caso4/Line Chart 4.png>)|
|inFlight|![](<graficos/parte2/graficos_caso3/inFlight in Network.nodeTx.transport.png>)|![](<graficos/parte2/graficos_caso4/inFlight in Network.nodeTx.transport.png>)|

# CONCLUSIONES:
### CASO 1:
<p>Comparando casos 1 con y sin control, podemos ver una reduccion significativa en la cantidad de paquetes perdidos gracias al uso de ACK's para el control de congestion.<br>Podemos ver el caracteristico "borde de sierra" presente en cwnd por la utilización del metodo AIMD en el calculo de sus ventanas. Asi como la estabilización de effectiveWindow a lo largo de la simulación.<p>

### CASO 2:
<p>Comparando casos 2 con y sin control, al igual que el caso anterior podemos ver una reduccion significativa en la perdida de paquetes.<br>
Podemos ver la notable ausencia de los bordes de sierra, ya que el ajuste ocurrira de forma tardía y será acompañada de notificaciones ECN constantes. Esto es notablemente obvio viendo la ocuacion del buffer rx, ya que recivira ECN's de Queue y llenara su buffer de selfmessage cuando envie un ACK marcado con ECN.<p>


# RESULTADOS DE COMPETICION:
| Metrica |  Calculo |
|----|----|
|goodput (pkt/s)|paquetes en Sink / 200s|
|lossRate (%)|100 × descartados / generados|
|avgDelay (s)|demora E2E promedio (Sink)|
|stability (pkt)|desvío estándar de effectiveWindow|


| Grupo |  goodput (pkt/s) | lossRate (%) | avgDelay (s) | stability (pkt) |
|----|----|----|----|----|
| 26 |  997/200 = 4,985 | 100*62/1979 = 3,132  | 45,155 | 4,178 |