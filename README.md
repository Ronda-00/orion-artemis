[README.md](https://github.com/user-attachments/files/26532337/README.md)
# Eyebit Tracker v1.3 — Orion Artemis II + Satélites

Programa de seguimiento de la nave Orion (misión Artemis II de NASA) y satélites en órbita baja, con interfaz gráfica en tiempo real.

**Autor:** EA5EMA ·( Ronda ) -> España

## Instalación

Se necesita Python 3.8 o superior y las siguientes librerías:

pip install ephem requests

Para arrancar:
python3 seguimiento_orion_montura.py

## Primer paso: configurar tu posición

Al abrir el programa, dentro de configuracion , en el panel derecho hay una sección **"Posición geográfica"** donde debes introducir:

- **Latitud** en grados decimales (ej: 39.49242)
- **Longitud** en grados decimales (negativo para oeste, ej: -1.30556)
- **Elevación** en metros sobre el nivel del mar
- **Lugar** — nombre libre (ej: "Residencia", "Colegio"). Este nombre aparece en el mapamundi cuando pasas el ratón por encima de tu posición. Si lo dejas vacío aparece el locator Maidenhead.
- **Locator** — cuadrícula Maidenhead. Puedes escribirlo aquí y pulsar el botón para que calcule latitud/longitud automáticamente, o al revés.

Pulsa * "Guardar" * para que se guarde la configuración.

También puedes elegir si quieres que las horas se muestren en * UTC * o en *hora local*.

## La carta polar

Es el gráfico circular grande en el centro. Representa el cielo visto desde tu posición:

- El *centro* es el zénit (justo encima de tu cabeza, 90° de elevación)
- El *borde exterior* es el horizonte (0° de elevación)
- * Norte** arriba, * Este** a la derecha, * Sur* abajo, * Oeste* a la izquierda
- Los círculos concéntricos marcan 30° y 60° de elevación

Sobre la carta se dibujan:

- * Trayectoria del satélite o nave seleccionada * — línea discontinua con 3 puntos:
  - **Punto de salida** (↑): en el horizonte, con azimut y hora
  - **Punto de máxima elevación** (▲): el punto más alto del pase, con elevación y hora
  - **Punto de puesta** (↓): en el horizonte, con azimut y hora
- **Trayectoria del Sol** — en amarillo (o azul si Orion está seleccionado). Solo se muestra cuando el Sol está sobre el horizonte. Mismos 3 puntos con salida, máximo y puesta.
- **Trayectoria de la Luna** — en gris. Solo se muestra cuando la Luna está sobre el horizonte. Mismos 3 puntos.
- **Posición actual** del Sol y la Luna como puntos sobre su trayectoria.

Los rótulos de los puntos nunca se solapan entre sí ni con las trayectorias gracias a un sistema de colocación inteligente que busca espacio libre en 24 direcciones.

Al pasar el ratón sobre cualquier trayectoria aparece un tooltip con azimut, elevación y hora de ese punto.

En la esquina inferior derecha hay rectángulos pulsables para mostrar/ocultar las trayectorias de Orion, Luna y Sol.

## El mapamundi

Debajo de la carta polar hay un mapa del mundo en proyección plana que muestra:

- **Tu posición** como un punto (con el nombre que hayas puesto en "Lugar" al pasar el ratón)
- **Cada satélite** como un punto con una letra (A, B, C...). Al pasar el ratón aparece el nombre.
- **El Sol** como un punto amarillo (o azul si Orion está seleccionado)
- **La Luna** como un punto gris (o un gajo de luna cuando Orion está seleccionado, para distinguirla de la nave)
- **Orion** como un punto amarillo cuando está seleccionado

El mapa se actualiza cada 10 segundos. Al hacer clic sobre un satélite en el mapa, se selecciona.

## Cómo funciona Orion (Artemis II)

Orion está en trayectoria cislunar — no orbita la Tierra como un satélite normal. Por eso **no se puede calcular con TLEs** (que solo sirven para órbitas terrestres con un solo cuerpo gravitatorio).

En su lugar, el programa consulta la **API de NASA JPL Horizons** por internet:

- URL: `https://ssd.jpl.nasa.gov/api/horizons.api`
- ID del target: * -1024 * (identificador de la nave Orion Artemis II en el catálogo de Horizons)
- El programa envía tus coordenadas geográficas y pide azimut y elevación cada 1 minuto
- Horizons devuelve la posición calculada con efemérides de múltiples cuerpos (Tierra + Luna + Sol)
- Se consultan 36 horas de datos (12h antes de ahora + 24h después) para capturar el pase completo
- El programa encuentra el pase que contiene la hora actual y dibuja solo ese arco
- Cada 10 minutos descarga datos nuevos automáticamente

Cuando seleccionas Orion en la lista, el programa detecta automáticamente que es un objeto cislunar y cambia de modo TLE a modo Horizons.

## Satélites normales (LEO)

Para los satélites normales (ISS, SO-50, FO-29, etc.):

- Se calculan localmente con la librería * PyEphem * usando el propagador SGP4
- Los datos orbitales se leen del fichero `mis_satelites.tle` en formato TLE estándar de 3 líneas
- Al arrancar el programa * actualiza automáticamente los TLEs * desde Celestrak por internet
- Calcula todos los pases de las próximas 48 horas y los muestra en una tabla
- Puedes navegar entre pases con los botones ◀ ▶

## Simulador de hora

En el panel derecho hay una sección para introducir una fecha y hora manualmente. Sirve para probar cómo se verá el cielo en cualquier momento:

- Activa el checkbox de simulador
- Introduce fecha (DD/MM/AAAA) y hora (HH:MM)
- La hora se interpreta en UTC o local según tu configuración
- Pulsa "Aplicar hora"
- * Todos los datos se recalculan *: trayectorias de satélites, Sol, Luna, Orion, mapamundi
- El reloj de la barra superior muestra "SIM" y la hora se detiene (no avanza)
- Al desactivar el simulador vuelve a hora real y recalcula todo

## Fichero TLE

El fichero `mis_satelites.tle` contiene los satélites que aparecen en la lista. Formato:

```
ISS (ZARYA)
1 25544U 98067A   26096.00498673  .00007825  00000+0  15107-3 0  9998
2 25544  51.6327 297.3095 0006349 277.1679  82.8588 15.48794122560566
```

Se pueden añadir o quitar satélites editando este fichero.

## Frecuencias de Artemis II (para radioaficionados)

- Downlink S-band: 2210.5 MHz, 2287.5 MHz, 2290.8 MHz
- La voz y telemetría van cifradas — no se puede decodificar
- Lo que sí se puede hacer: ver la señal en waterfall y medir Doppler
