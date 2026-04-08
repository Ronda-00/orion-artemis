#!/usr/bin/env python3
# ============================================================
#   S A T E L I T E   T R A C K E R   v2.0
#   Seguimiento de satélites con control de antena via ESP32
#   Unificación de seguimiento_Horario.py +
#                   seguimiento_Horario_Antihorario.py
#
#   la ia me ha unificado mi programa para que funcione
#   todo bajo el miosmo entorno y asi no abrir 3 programa
#             25 de marzo de 2026
#
#        uso dos servos controlados desde el macbook y 
#  por puerto serie le voy dando comando de moviemiento al esp32
#  para que vaya moviendo los dos servos
# ============================================================

#!/usr/bin/env python3
# =============================================================
#   S A T É L I T E   T R A C K E R   v3.0
#   EA5 · Valencia · 39.47°N  0.39°W  40m
#
#   Autor: generado para EA5 radioaficionado
#   Control de antena con dos servos via ESP32
#   Python 3.8+  |  pip install ephem pyserial
# =============================================================

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
import threading
import math
import time
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Dependencias opcionales ──────────────────────────────────
try:
    import ephem
    EPHEM_OK = True
except ImportError:
    EPHEM_OK = False
    print("AVISO: instala ephem:  pip install ephem")

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False
    print("AVISO: instala requests:  pip install requests")

import socket

try:
    import serial
    import serial.tools.list_ports
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False
    print("AVISO: instala pyserial:  pip install pyserial")

# =============================================================
#   C O N S T A N T E S
# =============================================================

APP_NAME      = "Eyebit Tracker"
APP_VERSION   = "1.4"
CONFIG_FILE   = Path.home() / ".satelite_tracker.json"
TLE_FILE      = Path("mis_satelites.tle")
DEG           = 180.0 / math.pi
HORAS_TABLA   = 48          # horas hacia adelante para tabla de pasos
ELEV_MIN      = 5.0         # elevación mínima para considerar un pase útil

# Observador por defecto (Valencia EA5)
OBS_LAT  = "39.47222"
OBS_LON  = "-0.39556"
OBS_ELEV = 40

# Fuentes TLE de Celestrak
CELESTRAK_GROUPS = {
    "Estaciones espaciales": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=TLE",
    "Amateur (AMSAT)":       "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=TLE",
    "100 mas visibles":      "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=TLE",
    "CubeSats":              "https://celestrak.org/NORAD/elements/gp.php?GROUP=cubesat&FORMAT=TLE",
    "Clima / Meteo":         "https://celestrak.org/NORAD/elements/gp.php?GROUP=noaa&FORMAT=TLE",
}

# API Celestrak para buscar por nombre/NORAD
CELESTRAK_NAME_URL  = "https://celestrak.org/SOCRATES/query.php?CATNR={norad}&TYPE=2&LIMITS=5"
CELESTRAK_NORAD_URL = "https://celestrak.org/satcat/tle.php?CATNR={norad}"
CELESTRAK_SEARCH    = "https://celestrak.org/SOCRATES/query.php?NAME={name}&TYPE=2&LIMITS=10"

# TLEs de reserva (por si no hay internet al arrancar)
FALLBACK_TLES = """\
ISS (ZARYA)
1 25544U 98067A   24001.50000000  .00001234  00000-0  23456-4 0  9990
2 25544  51.6416 120.0000 0003000  80.0000  75.0000 15.49000000000001
OSCAR 7 (AO-7)
1 07530U 74089B   24001.89296862 -.00000025  00000-0  12802-3 0  9992
2 07530 101.8425  41.5499 0011983 216.3620 157.9766 12.53647703119002
FUNCUBE-1 (AO-73)
1 39444U 13066AE  24001.52130418  .00000395  00000-0  54209-4 0  9991
2 39444  97.5771  59.4655 0059063 122.0998 238.5969 14.82333807393073
SAUDISAT 1C (SO-50)
1 27607U 02058C   24001.05783550  .00000053  00000-0  28045-4 0  9997
2 27607  64.5546 288.3969 0031043  62.9327 297.4937 14.75719732979753
JAS-2 (FO-29)
1 24278U 96046B   24001.51719071 -.00000049  00000-0 -15585-4 0  9998
2 24278  98.5768 148.8275 0351102  51.2374 311.9590 13.53101997212841
RS-44
1 44909U 19096E   24001.75522303  .00000017  00000-0  28663-4 0  9990
2 44909  82.5253 180.3753 0216740 331.1443  27.7809 12.79708694 55836
ORION (ARTEMIS II)
1 99999U 26001A   26091.00000000  .00000000  00000-0  00000-0 0  9990
2 99999  28.5000 000.0000 9000000 000.0000 000.0000  0.03000000    10
"""

# =============================================================
#   U T I L I D A D E S   T L E
# =============================================================

def parse_tle_text(text: str) -> dict:
    """Parsea texto TLE → {nombre: (linea1, linea2)}"""
    sats = {}
    lines = [l.rstrip() for l in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('#'):
            i += 1
            continue
        if line.startswith('1 ') or line.startswith('2 '):
            i += 1
            continue
        # Es un nombre de satélite
        name = line
        j = i + 1
        l1 = l2 = ''
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].strip().startswith('1 '):
            l1 = lines[j].strip()
            j += 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].strip().startswith('2 '):
            l2 = lines[j].strip()
            j += 1
        if l1 and l2:
            sats[name] = (l1, l2)
            i = j
        else:
            i += 1
    return sats


def save_tle_file(sats: dict, path: Path):
    """Guarda dict de satélites en archivo TLE"""
    with open(path, 'w', encoding='utf-8') as f:
        for name, (l1, l2) in sats.items():
            f.write(f"{name}\n{l1}\n{l2}\n")


def download_url(url: str, timeout: int = 10) -> str | None:
    """Descarga texto de una URL. Devuelve None si falla."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': f'EyebitTracker/{APP_VERSION} (EA5)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception:
        return None


def search_celestrak_by_name(name: str) -> dict:
    """Busca satélite por nombre en Celestrak (API nueva gp.php)."""
    encoded = urllib.parse.quote(name)
    url = f"https://celestrak.org/NORAD/elements/gp.php?NAME={encoded}&FORMAT=TLE"
    text = download_url(url)
    if text:
        return parse_tle_text(text)
    return {}


def search_celestrak_by_norad(norad: str) -> dict:
    """Busca satélite por número NORAD en Celestrak (API nueva gp.php)."""
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad.strip()}&FORMAT=TLE"
    text = download_url(url)
    if text:
        return parse_tle_text(text)
    return {}


def latlon_to_locator(lat, lon):
    """Convierte lat/lon a Maidenhead locator (6 caracteres)."""
    try:
        lat = float(lat) + 90
        lon = float(lon) + 180
        a = int(lon / 20)
        b = int(lat / 10)
        lon -= a * 20
        lat -= b * 10
        c = int(lon / 2)
        d = int(lat)
        lon -= c * 2
        lat -= d
        e = int(lon * 12)
        f = int(lat * 24)
        return f"{chr(65+a)}{chr(65+b)}{c}{d}{chr(97+e)}{chr(97+f)}"
    except Exception:
        return ""

def locator_to_latlon(loc):
    """Convierte Maidenhead locator a (lat, lon). Devuelve (None,None) si inválido."""
    try:
        loc = loc.strip().upper()
        if len(loc) < 4:
            return None, None
        lon = (ord(loc[0]) - 65) * 20 - 180
        lat = (ord(loc[1]) - 65) * 10 - 90
        lon += int(loc[2]) * 2
        lat += int(loc[3])
        if len(loc) >= 6:
            lon += (ord(loc[4]) - 65) / 12 + 1/24
            lat += (ord(loc[5]) - 65) / 24 + 1/48
        else:
            lon += 1
            lat += 0.5
        return round(lat, 5), round(lon, 5)
    except Exception:
        return None, None

def get_norad_from_tle_line(line1: str) -> str:
    """Extrae número NORAD de la línea 1 del TLE."""
    try:
        return line1[2:7].strip()
    except Exception:
        return "?"


# =============================================================
#   O R I O N  /  D E E P   S P A C E   (NASA Horizons)
# =============================================================

# Objetos cislunar/deep space que usan Horizons en vez de TLEs
HORIZONS_OBJECTS = {
    "ORION (ARTEMIS II)": "-1024",
}
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
MOON_TARGET = "301"  # Luna en Horizons


def query_horizons_track(target, obs_lat, obs_lon, obs_elev, hours=24, step_min=5):
    """
    Consulta NASA Horizons y devuelve lista de (az, el) para un target.
    Sirve para Orion, Luna, o cualquier objeto.
    """
    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%d %H:%M")
    stop = (now + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")
    lat_f = float(obs_lat)
    lon_f = float(obs_lon)
    alt_km = float(obs_elev) / 1000.0

    body = (
        f"format=json"
        f"&COMMAND='{target}'"
        f"&OBJ_DATA=NO"
        f"&MAKE_EPHEM=YES"
        f"&EPHEM_TYPE=OBSERVER"
        f"&CENTER='coord@399'"
        f"&COORD_TYPE=GEODETIC"
        f"&SITE_COORD='{lon_f},{lat_f},{alt_km}'"
        f"&START_TIME='{start}'"
        f"&STOP_TIME='{stop}'"
        f"&STEP_SIZE='{step_min} m'"
        f"&QUANTITIES='4'"
        f"&ANG_FORMAT=DEG"
        f"&TIME_ZONE='+00:00'"
    )
    try:
        req = urllib.request.Request(
            HORIZONS_URL, data=body.encode(),
            headers={'User-Agent': 'OrionTracker/4.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        result = data.get("result", "")
        points = []
        in_data = False
        for line in result.split("\n"):
            if "$$SOE" in line:
                in_data = True
                continue
            if "$$EOE" in line:
                break
            if in_data and line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        az = float(parts[3])
                        el = float(parts[4])
                        points.append((az, el))
                    except (ValueError, IndexError):
                        continue
        return points
    except Exception:
        return []


def is_horizons_object(sat_name: str) -> bool:
    """Devuelve True si este objeto usa NASA Horizons en vez de TLEs."""
    return sat_name in HORIZONS_OBJECTS


def get_horizons_azel(sat_name: str, obs_lat: str, obs_lon: str, obs_elev: int):
    """
    Descarga azimut/elevación/distancia de un objeto desde NASA Horizons.
    Devuelve dict {az, el, dist_km, ra, dec} o None si falla.
    """
    target = HORIZONS_OBJECTS.get(sat_name, "-180")
    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%d %H:%M")
    stop = (now + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")

    lat_f = float(obs_lat)
    lon_f = float(obs_lon)
    alt_km = float(obs_elev) / 1000.0

    body = (
        f"format=json"
        f"&COMMAND='{target}'"
        f"&OBJ_DATA=NO"
        f"&MAKE_EPHEM=YES"
        f"&EPHEM_TYPE=OBSERVER"
        f"&CENTER='coord@399'"
        f"&COORD_TYPE=GEODETIC"
        f"&SITE_COORD='{lon_f},{lat_f},{alt_km}'"
        f"&START_TIME='{start}'"
        f"&STOP_TIME='{stop}'"
        f"&STEP_SIZE='1 m'"
        f"&QUANTITIES='4'"
        f"&ANG_FORMAT=DEG"
        f"&TIME_ZONE='+00:00'"
    )

    try:
        req = urllib.request.Request(
            HORIZONS_URL,
            data=body.encode(),
            headers={'User-Agent': 'OrionTracker/4.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        result = data.get("result", "")

        lines = result.split("\n")
        in_data = False
        for line in lines:
            if "$$SOE" in line:
                in_data = True
                continue
            if "$$EOE" in line:
                break
            if in_data and line.strip():
                # Formato: " 2026-Apr-04 16:35 *    52.180277 -71.143626"
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        az = float(parts[3])
                        el = float(parts[4])
                        return {
                            "az": az, "el": el,
                            "ra": 0, "dec": 0,
                            "dist_km": 0,
                        }
                    except (ValueError, IndexError):
                        continue
    except Exception:
        pass
    return None


# =============================================================
#   A Z - G T i X   M O N T U R A   WiFi (SynScan)
# =============================================================

class SynScanMount:
    """Control de AZ-GTiX via WiFi (protocolo SynScan TCP)."""

    def __init__(self, ip="192.168.4.1", port=11880):
        self.ip = ip
        self.port = port
        self.sock = None
        self.connected = False

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.connected = True
            return True
        except Exception:
            self.sock = None
            self.connected = False
            return False

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None
        self.connected = False

    def _send_cmd(self, cmd):
        if not self.sock:
            return None
        try:
            self.sock.send(cmd.encode())
            resp = self.sock.recv(256).decode().strip()
            return resp
        except Exception:
            return None

    def _deg_to_hex(self, degrees):
        val = int((degrees % 360) / 360.0 * 16777216)
        return f"{val:06X}"

    def goto_azalt(self, az, alt):
        if alt < 0:
            return False
        az_hex = self._deg_to_hex(az)
        alt_hex = self._deg_to_hex(alt)
        cmd = f"b{az_hex},{alt_hex}"
        resp = self._send_cmd(cmd)
        return resp is not None and resp.startswith("#")

    def get_position(self):
        resp = self._send_cmd("z")
        if resp and len(resp) >= 13:
            try:
                az = int(resp[0:6], 16) / 16777216.0 * 360.0
                alt = int(resp[7:13], 16) / 16777216.0 * 360.0
                if alt > 180:
                    alt -= 360
                return az, alt
            except:
                pass
        return None, None


# Variable global de montura (se crea en la App)
syncan_mount = None


# =============================================================
#   C O N F I G U R A C I Ó N   P E R S I S T E N T E
# =============================================================

def load_config() -> dict:
    defaults = {
        "serial_port": "",
        "serial_baud": 9600,
        "obs_lat":     OBS_LAT,
        "obs_lon":     OBS_LON,
        "obs_elev":    OBS_ELEV,
        "interval_s":  3,
        "track_mode":  "auto",
        "window_geo":  "1200x800",
        "use_utc":     True,
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# =============================================================
#   C Á L C U L O   D E   P A S O S
# =============================================================

def compute_next_passes(sat_name: str, tle1: str, tle2: str,
                        obs_lat: str, obs_lon: str, obs_elev: int,
                        hours: float = 48.0, min_el: float = 5.0,
                        start_time=None) -> list:
    """
    Calcula todos los pases de un satélite en las próximas `hours` horas.
    Devuelve lista de dicts con: rise_time, rise_az, max_el, max_el_time,
    set_time, set_az, duration_s, sentido
    start_time: datetime UTC (si None, usa hora actual)
    """
    if not EPHEM_OK:
        return []
    results = []
    try:
        satellite = ephem.readtle(sat_name, tle1, tle2)
        obs = ephem.Observer()
        obs.lat       = obs_lat
        obs.lon       = obs_lon
        obs.elevation = int(obs_elev)
        obs.horizon   = str(min_el)
        if start_time:
            obs.date = start_time.replace(tzinfo=None)
        else:
            obs.date = datetime.now(timezone.utc).replace(tzinfo=None)

        limit = obs.date + hours / 24.0
        scan  = obs.date

        while scan < limit:
            obs.date = scan
            try:
                info = obs.next_pass(satellite)
            except Exception:
                break

            rise_t, rise_az_rad, max_t, max_alt_rad, set_t, set_az_rad = info

            if rise_t is None or set_t is None:
                break
            if rise_t >= limit:
                break

            duration_s = (set_t - rise_t) * 86400.0
            max_el_deg = max_alt_rad * DEG
            rise_az    = rise_az_rad * DEG
            set_az     = set_az_rad  * DEG

            # Sentido del pase (horario o antihorario)
            sentido = "Horario" if set_az > rise_az else "Antihorario"

            # Guardar siempre en UTC aware — fmt_time convierte a local si hace falta
            def ephem_to_utc(et):
                return ephem.Date(et).datetime().replace(tzinfo=timezone.utc)

            results.append({
                "sat_name":  sat_name,
                "rise_time": ephem_to_utc(rise_t),
                "rise_az":   rise_az,
                "max_el":    max_el_deg,
                "max_time":  ephem_to_utc(max_t),
                "set_time":  ephem_to_utc(set_t),
                "set_az":    set_az,
                "duration_s": int(duration_s),
                "sentido":   sentido,
                "rise_ephem": rise_t,
                "set_ephem":  set_t,
            })

            # Avanzar al siguiente pase (set_time + 1 minuto)
            scan = set_t + 1.0 / 1440.0

    except Exception:
        pass

    return results


# =============================================================
#   A P L I C A C I Ó N   P R I N C I P A L
# =============================================================

class App:
    """Aplicación principal de seguimiento de satélites."""

    # ── Paleta de colores ────────────────────────────────────
    C = {
        "bg":       "#0a0a0a",   # negro base
        "panel":    "#0f0f0f",   # gris muy oscuro
        "border":   "#181818",   # borde sutil
        "border2":  "#222222",   # borde medio
        "accent":   "#708090",   # gris azulado medio (títulos) — no deslumbra
        "accent2":  "#252530",   # selección
        "green":    "#507050",   # verde oscuro apagado
        "yellow":   "#807050",   # dorado oscuro apagado
        "red":      "#703030",   # rojo oscuro apagado
        "orange":   "#705040",   # naranja oscuro apagado
        "text":     "#d0d0d0",   # texto gris claro — bien visible
        "muted":    "#808080",   # texto secundario gris medio
        "grid":     "#0c0c0c",   # fondo listbox
        "hot":      "#703030",
        "warm":     "#807050",
        "cool":     "#506070",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg  = load_config()

        # Estado de la aplicación
        self.satellites:   dict  = {}          # {nombre: (l1, l2)}
        self.selected_sat: str   = ""
        self.tracking:     bool  = False
        self.track_thread         = None
        self.serial_conn          = None
        self.pass_track:   list  = []          # [(az,el),...] pase actual
        self.future_track: list  = []          # [(az,el),...] trayectoria calculada
        self.moon_track:   list  = []          # [(az,el),...] trayectoria Luna (solo Orion)
        self.moon_rise_utc = None
        self.moon_set_utc  = None
        self.moon_max_utc  = None
        self._moon_screen_pts = []  # [(px, py, az, el, time_str), ...]
        self.az_now:       float = 0.0
        self.el_now:       float = 0.0
        self.sentido:      str   = ""
        self.v0_az:        float = 0.0
        self.table_passes: list  = []          # filas calculadas para la tabla
        self.table_calc_thread    = None
        self.table_stop:   bool  = False
        self.sat_passes:   list  = []          # pases del satélite seleccionado
        self.pass_index:   int   = 0           # índice del pase mostrado en mapa
        self._show_orion_phase: bool = True    # ya no se usa para intermitencia
        self._orion_visible = True            # Orion activo al arrancar
        self._luna_visible = False            # Luna desactivada al arrancar
        self.sun_track = []                   # [(az,el,time_str),...] 24h Sun trajectory
        self._sun_visible = False             # Sun toggle
        self._sun_rise_utc = None
        self._sun_max_utc = None
        self._sun_set_utc = None
        self._sun_screen_pts = []
        self._legend_rects = []               # [(x1,y1,x2,y2,layer_name), ...]
        self._last_track_refresh: float = 0    # timestamp última actualización trayectoria
        self._last_hover_time: float = 0       # timestamp último hover activo
        self._last_auto_fetch: float = 0.0
        self._orion_subpoint = None   # (lat, lon) sub-punto de Orion     # timestamp último fetch auto-posición Horizons
        self._last_horizons_refresh: float = 0.0

        # Construir interfaz
        self._setup_window()
        self._build_ui()
        self._load_satellites()
        # Auto-actualizar TLEs al arrancar
        self._auto_update_tles_startup()
        self._try_serial_connect()
        self._tick_clock()
        self._tick_orion_moon_toggle()
        self._tick_auto_position()

    # ── Ventana ──────────────────────────────────────────────

    def _setup_window(self):
        self.root.title(f"🛰  SATÉLITE TRACKER v{APP_VERSION}  by EA5EMA")
        self.root.geometry(self.cfg.get("window_geo", "1200x800"))
        self.root.configure(bg=self.C["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.tracking   = False
        self.table_stop = True
        self.cfg["window_geo"] = self.root.geometry()
        save_config(self.cfg)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.root.destroy()

    # ── Construcción UI ──────────────────────────────────────

    def _build_ui(self):
        # Barra superior
        self._build_topbar()

        # Notebook de pestañas principal
        nb_style = ttk.Style()
        nb_style.theme_use('default')
        nb_style.configure('Custom.TNotebook',
                           background=self.C["bg"],
                           borderwidth=0)
        nb_style.configure('Custom.TNotebook.Tab',
                           background=self.C["panel"],
                           foreground=self.C["muted"],
                           font=("Courier New", 9, "bold"),
                           padding=[14, 6],
                           borderwidth=0)
        nb_style.map('Custom.TNotebook.Tab',
                     background=[('selected', self.C["border2"])],
                     foreground=[('selected', self.C["accent"])])

        self.nb = ttk.Notebook(self.root, style='Custom.TNotebook')
        self.nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        # Pestaña 1: Seguimiento en tiempo real
        self.tab_track = tk.Frame(self.nb, bg=self.C["bg"])
        self.nb.add(self.tab_track, text="  🛰  SEGUIMIENTO  ")
        self._build_tracking_tab(self.tab_track)

        # Pestaña 2: Tabla de próximos pasos
        self.tab_table = tk.Frame(self.nb, bg=self.C["bg"])
        self.nb.add(self.tab_table, text="  📅  PRÓXIMOS PASOS  ")
        self._build_table_tab(self.tab_table)

        # Pestaña 3: Gestión de satélites
        self.tab_sats = tk.Frame(self.nb, bg=self.C["bg"])
        self.nb.add(self.tab_sats, text="  ⚙  SATÉLITES / TLE  ")
        self._build_sats_tab(self.tab_sats)

        # Pestaña 4: Configuración
        self.tab_cfg = tk.Frame(self.nb, bg=self.C["bg"])
        self.nb.add(self.tab_cfg, text="  🔧  CONFIGURACIÓN  ")
        self._build_config_tab(self.tab_cfg)

    # ── Barra superior ───────────────────────────────────────

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=self.C["panel"], height=46)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text=f"🛰 SATÉLITE TRACKER v{APP_VERSION}",
                 font=("Courier New", 13, "bold"),
                 fg=self.C["accent"], bg=self.C["panel"]).pack(side=tk.LEFT, padx=(16,4))
        tk.Label(bar, text="by EA5EMA",
                 font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["panel"]).pack(side=tk.LEFT, padx=(0,12))

        self.lbl_callsign = tk.Label(bar, text="", bg=self.C["panel"])

        # Estado serie (topbar)
        self.lbl_serial_top = tk.Label(bar, text="● SIN PUERTO",
                                        font=("Courier New", 9, "bold"),
                                        fg=self.C["red"], bg=self.C["panel"])
        self.lbl_serial_top.pack(side=tk.RIGHT, padx=16)

        self.lbl_time = tk.Label(bar, text="",
                                  font=("Courier New", 11, "bold"),
                                  fg=self.C["green"], bg=self.C["panel"])
        self.lbl_time.pack(side=tk.RIGHT, padx=12)

    # ── Pestaña SEGUIMIENTO ──────────────────────────────────

    def _build_tracking_tab(self, parent):
        # Layout: izquierda (lista + controles) | centro (mapa) | derecha (log)
        left = tk.Frame(parent, bg=self.C["bg"], width=240)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 4), pady=6)
        left.pack_propagate(False)

        center = tk.Frame(parent, bg=self.C["bg"])
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=6)

        right = tk.Frame(parent, bg=self.C["bg"], width=230)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 6), pady=6)
        right.pack_propagate(False)

        # Izquierda
        self._build_sat_selector(left)
        self._build_serial_panel(left)
        self._build_control_panel(left)

        # Centro: mapa polar arriba, mapamundi abajo
        self._build_polar_canvas(center)
        self._build_telemetry_bar(center)
        self._build_world_map(center)

        # Derecha
        self._build_log_panel(right)

    def _build_sat_selector(self, parent):
        f = self._panel(parent, "SATÉLITE")
        f.pack(fill=tk.X, pady=(0, 5))

        # Filtro de búsqueda
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self._filter_listbox())
        tk.Entry(f, textvariable=self.search_var,
                 font=("Courier New", 9),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"],
                 relief=tk.FLAT, bd=3).pack(fill=tk.X, pady=(0, 3))

        # Listbox
        lf = tk.Frame(f, bg=self.C["panel"])
        lf.pack(fill=tk.BOTH)
        sb = tk.Scrollbar(lf, bg=self.C["border"])
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sat_listbox = tk.Listbox(
            lf, height=10, font=("Courier New", 9),
            bg=self.C["grid"], fg=self.C["text"],
            selectbackground=self.C["accent2"],
            selectforeground="#606060",
            relief=tk.FLAT, bd=0,
            yscrollcommand=sb.set,
            activestyle='none')
        self.sat_listbox.pack(fill=tk.BOTH)
        sb.config(command=self.sat_listbox.yview)
        self.sat_listbox.bind('<<ListboxSelect>>', self._on_sat_select)

        # Info satélite seleccionado
        self.lbl_sat_info = tk.Label(f, text="Sin selección",
                                      font=("Courier New", 8),
                                      fg=self.C["muted"], bg=self.C["panel"],
                                      wraplength=210, justify=tk.LEFT)
        self.lbl_sat_info.pack(anchor=tk.W, pady=2)

    def _build_serial_panel(self, parent):
        f = self._panel(parent, "PUERTO SERIE → ESP32")
        f.pack(fill=tk.X, pady=(0, 5))

        row = tk.Frame(f, bg=self.C["panel"])
        row.pack(fill=tk.X, pady=2)

        self.port_var = tk.StringVar(value=self.cfg.get("serial_port", ""))
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var,
                                        font=("Courier New", 8), width=16)
        self.port_combo.pack(side=tk.LEFT)

        tk.Button(row, text="⟳", command=self._refresh_ports,
                  font=("Courier New", 9), fg=self.C["muted"],
                  bg=self.C["border"], relief=tk.FLAT, bd=0,
                  padx=4, cursor="hand2").pack(side=tk.LEFT, padx=2)

        row2 = tk.Frame(f, bg=self.C["panel"])
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Baud:", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["panel"]).pack(side=tk.LEFT)
        self.baud_var = tk.StringVar(value=str(self.cfg.get("serial_baud", 9600)))
        ttk.Combobox(row2, textvariable=self.baud_var,
                     values=["4800","9600","19200","38400","57600","115200"],
                     font=("Courier New", 8), width=8).pack(side=tk.LEFT, padx=4)

        self.btn_serial = tk.Button(f, text="CONECTAR",
                                     command=self._toggle_serial,
                                     font=("Courier New", 9, "bold"),
                                     fg=self.C["green"], bg=self.C["border"],
                                     relief=tk.FLAT, bd=0, pady=3, cursor="hand2")
        self.btn_serial.pack(fill=tk.X, pady=3)

        self.lbl_serial = tk.Label(f, text="● Desconectado",
                                    font=("Courier New", 8),
                                    fg=self.C["red"], bg=self.C["panel"])
        self.lbl_serial.pack()

        self._refresh_ports()

    def _build_control_panel(self, parent):
        f = self._panel(parent, "CONTROL ANTENA")
        f.pack(fill=tk.X, pady=(0, 5))

        # Modo
        tk.Label(f, text="Modo azimut:", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["panel"]).pack(anchor=tk.W)
        self.mode_var = tk.StringVar(value=self.cfg.get("track_mode", "auto"))
        for txt, val in [("Automático", "auto"),
                         ("Forzar Horario ↻", "cw"),
                         ("Forzar Antihorario ↺", "ccw")]:
            tk.Radiobutton(f, text=txt, variable=self.mode_var, value=val,
                           font=("Courier New", 8),
                           fg=self.C["text"], bg=self.C["panel"],
                           selectcolor=self.C["bg"],
                           activebackground=self.C["panel"]).pack(anchor=tk.W)

        tk.Frame(f, bg=self.C["border"], height=1).pack(fill=tk.X, pady=4)

        # Intervalo
        tk.Label(f, text="Intervalo (seg):", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["panel"]).pack(anchor=tk.W)
        self.interval_var = tk.IntVar(value=self.cfg.get("interval_s", 3))
        tk.Scale(f, from_=1, to=15, orient=tk.HORIZONTAL,
                 variable=self.interval_var,
                 font=("Courier New", 7),
                 bg=self.C["panel"], fg=self.C["text"],
                 troughcolor=self.C["border"],
                 highlightthickness=0,
                 activebackground=self.C["accent"]).pack(fill=tk.X)

        tk.Frame(f, bg=self.C["border"], height=1).pack(fill=tk.X, pady=4)

        # Botón START/STOP
        self.btn_track = tk.Button(f, text="▶  INICIAR SEGUIMIENTO",
                                    command=self._toggle_tracking,
                                    font=("Courier New", 10, "bold"),
                                    fg=self.C["accent"], bg=self.C["border2"],
                                    relief=tk.FLAT, bd=0, pady=6, cursor="hand2")
        self.btn_track.pack(fill=tk.X, pady=(4, 2))

        # Botón calcular trayectoria
        tk.Button(f, text="📡  Calcular trayectoria",
                  command=self._calc_single_pass,
                  font=("Courier New", 8),
                  fg=self.C["yellow"], bg=self.C["border"],
                  relief=tk.FLAT, bd=0, pady=3, cursor="hand2").pack(fill=tk.X)

    def _build_polar_canvas(self, parent):
        # Cabecera: título + contador de pases + botones navegación
        top = tk.Frame(parent, bg=self.C["bg"])
        top.pack(fill=tk.X, padx=4, pady=(0,2))
        tk.Label(top, text="MAPA POLAR", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["bg"]).pack(side=tk.LEFT)
        self.lbl_pass_counter = tk.Label(top, text="",
                                          font=("Courier New", 8),
                                          fg=self.C["muted"], bg=self.C["bg"])
        self.lbl_pass_counter.pack(side=tk.LEFT, padx=8)
        tk.Button(top, text="◀",
                  command=self._prev_pass,
                  font=("Courier New", 8, "bold"),
                  fg=self.C["text"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, padx=6, pady=1,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="▶",
                  command=self._next_pass,
                  font=("Courier New", 8, "bold"),
                  fg=self.C["text"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, padx=6, pady=1,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)

        # Canvas polar — ocupa todo el espacio restante
        self.canvas = tk.Canvas(parent, bg=self.C["bg"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=4)
        self.canvas.bind('<Configure>', lambda e: self._draw_polar())
        self.canvas.bind('<Motion>', self._on_polar_motion)
        self.canvas.bind('<Button-1>', self._on_polar_click)
        self._polar_tooltip = None  # canvas item id del tooltip
        self._track_screen_pts = []  # [(px, py, az, el, time_str), ...]

    def _build_telemetry_bar(self, parent):
        bar = tk.Frame(parent, bg=self.C["panel"])
        bar.pack(fill=tk.X, padx=4, pady=(4, 0))

        self._telem_labels = {}
        fields = [
            ("AZ",        "lbl_az",      ""),
            ("EL",        "lbl_el",      ""),
            ("SENTIDO",   "lbl_sentido", ""),
            ("AZ MOTOR",  "lbl_az_mot",  ""),
            ("EL MOTOR",  "lbl_el_mot",  ""),
        ]
        for title, key, default in fields:
            box = tk.Frame(bar, bg=self.C["border"], padx=1, pady=1)
            box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=4)
            inner = tk.Frame(box, bg=self.C["panel"])
            inner.pack(fill=tk.BOTH, expand=True)
            tk.Label(inner, text=title, font=("Courier New", 7),
                     fg=self.C["muted"], bg=self.C["panel"]).pack()
            lbl = tk.Label(inner, text=default,
                           font=("Courier New", 13, "bold"),
                           fg=self.C["accent"], bg=self.C["panel"])
            lbl.pack()
            self._telem_labels[key] = lbl

    def _build_world_map(self, parent):
        """Mapamundi con todos los satélites en tiempo real."""
        hdr = tk.Frame(parent, bg=self.C["bg"])
        hdr.pack(fill=tk.X, padx=4, pady=(4,0))
        tk.Label(hdr, text="MAPA MUNDIAL", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["bg"]).pack(side=tk.LEFT)
        self.lbl_obs_dot = tk.Label(hdr, text="● Valencia",
                                     font=("Courier New", 7),
                                     fg="#404040", bg=self.C["bg"])
        self.lbl_obs_dot.pack(side=tk.LEFT, padx=8)

        self.world_canvas = tk.Canvas(parent, bg="#060606",
                                       highlightthickness=0, height=160)
        self.world_canvas.pack(fill=tk.X, padx=4, pady=(2,4))
        self.world_canvas.bind('<Configure>', lambda e: self._draw_world())
        self.world_canvas.bind('<Button-1>', self._on_world_click)
        self.world_canvas.bind('<Motion>', self._on_world_motion)
        self._world_sat_pts = []  # [(sx, sy, name), ...]
        self._world_tooltip = None

        # Iniciar bucle de actualización del mapa mundial
        self._world_update()

    def _world_latlon_to_xy(self, lat, lon, w, h):
        x = (lon + 180) / 360 * w
        y = (90 - lat) / 180 * h
        return x, y

    def _sat_position_now(self, name):
        """Calcula lat/lon actual de un satélite con ephem.
        Para Orion: usa RA/DEC de la última consulta Horizons → sub-punto."""
        if is_horizons_object(name):
            # Usar az_now/el_now no sirve (es desde Valencia)
            # Calcular sub-punto desde RA/DEC via Horizons (cacheado)
            if hasattr(self, '_orion_subpoint') and self._orion_subpoint:
                return self._orion_subpoint
            return None
        if not EPHEM_OK or name not in self.satellites:
            return None
        try:
            l1, l2 = self.satellites[name]
            sat = ephem.readtle(name, l1, l2)
            obs = ephem.Observer()
            obs.lat  = self.cfg.get("obs_lat", OBS_LAT)
            obs.lon  = self.cfg.get("obs_lon", OBS_LON)
            obs.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
            obs.date = self._get_now().replace(tzinfo=None)
            sat.compute(obs)
            lat = sat.sublat * DEG
            lon = sat.sublong * DEG
            return lat, lon
        except Exception:
            return None

    def _draw_world(self):
        c = self.world_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return
        c.delete("all")

        # Fondo
        c.create_rectangle(0, 0, w, h, fill="#060606", outline="")

        # Grid
        for lon in range(-180, 181, 30):
            x = (lon + 180) / 360 * w
            c.create_line(x, 0, x, h, fill="#0f0f0f", width=1)
        for lat in range(-90, 91, 30):
            y = (90 - lat) / 180 * h
            col = "#1a1a1a" if lat == 0 else "#0f0f0f"
            c.create_line(0, y, w, y, fill=col, width=1)

        # Borde
        c.create_rectangle(0, 0, w-1, h-1, outline="#1a1a1a", fill="")

        # Contorno de continentes (coordenadas [lat, lon])
        # Continentes: (poligono, color_relleno, color_borde)
        continentes = [
            # Europa
            ([(71,28),(70,18),(63,5),(58,5),(51,-5),(44,-9),(36,-6),(36,3),
              (41,3),(44,8),(44,15),(41,19),(37,15),(38,26),(41,29),(42,28),
              (47,22),(48,17),(51,14),(54,14),(56,21),(60,25),(65,26),(71,28)],
             "#131313","#2a2a2a"),
            # Africa
            ([(37,10),(37,37),(12,44),(12,51),(0,42),(-11,40),(-26,33),
              (-34,26),(-34,18),(-22,14),(-17,12),(-5,10),(5,3),(4,-9),
              (10,-16),(15,-17),(21,-17),(32,-9),(37,10)],
             "#131313","#2a2a2a"),
            # Asia — separada y con contorno más claro
            ([(71,30),(65,35),(55,38),(50,30),(47,22),(42,28),(41,29),(37,37),
              (40,52),(45,60),(50,58),(55,60),(55,80),(50,80),(45,75),(35,75),
              (25,68),(22,70),(12,77),(8,77),(10,100),(10,105),(22,114),
              (25,120),(35,125),(45,135),(55,130),(60,140),(71,140),(71,30)],
             "#161616","#303030"),
            # Extremo oriente / Sudeste Asiático
            ([(22,114),(10,105),(5,100),(0,104),(0,108),(-8,115),(-8,125),
              (0,130),(10,125),(18,110),(22,114)],
             "#161616","#303030"),
            # América del Norte
            ([(70,-140),(70,-95),(83,-85),(83,-65),(72,-65),(65,-60),(60,-65),
              (47,-53),(47,-64),(44,-66),(42,-70),(35,-75),(25,-80),(25,-90),
              (20,-87),(15,-83),(8,-77),(10,-85),(15,-90),(18,-92),(22,-90),
              (25,-98),(30,-110),(32,-117),(37,-122),(48,-124),(55,-130),
              (60,-137),(65,-137),(70,-140)],
             "#131313","#2a2a2a"),
            # América del Sur — contorno más claro para distinguirla
            ([(8,-77),(8,-60),(10,-62),(0,-50),(-5,-35),(-10,-37),(-15,-38),
              (-22,-42),(-28,-48),(-34,-52),(-38,-57),(-45,-65),(-52,-68),
              (-56,-68),(-50,-74),(-45,-65),(-40,-62),(-34,-58),(-22,-42),
              (-15,-35),(-5,-35),(0,-50),(8,-60),(8,-77)],
             "#181818","#353535"),
            # Australia
            ([(-15,130),(-15,137),(-12,136),(-12,141),(-17,146),(-22,150),
              (-28,154),(-38,147),(-38,140),(-32,132),(-32,125),(-22,113),
              (-17,122),(-15,130)],
             "#131313","#2a2a2a"),
            # Groenlandia
            ([(83,-45),(76,-18),(72,-22),(68,-28),(64,-40),(64,-52),(68,-52),
              (72,-58),(76,-65),(83,-45)],
             "#131313","#252525"),
        ]

        for poly, fill, outline in continentes:
            pts = []
            for item in poly:
                if isinstance(item, tuple):
                    lat, lon = item
                    x, y = self._world_latlon_to_xy(lat, lon, w, h)
                    pts += [x, y]
            if len(pts) >= 4:
                c.create_polygon(pts, outline=outline, fill=fill,
                                 width=1, smooth=False)

        # Punto del observador (Valencia)
        try:
            obs_lat = float(self.cfg.get("obs_lat", OBS_LAT))
            obs_lon = float(self.cfg.get("obs_lon", OBS_LON))
            ox, oy = self._world_latlon_to_xy(obs_lat, obs_lon, w, h)
            c.create_oval(ox-3, oy-3, ox+3, oy+3,
                          fill="#303030", outline="#606060", width=1)
            _loc_name = self.cfg.get("obs_name", "").strip()
            if not _loc_name:
                _loc_name = latlon_to_locator(obs_lat, obs_lon)
            self._world_extra_pts = [(ox, oy, _loc_name, "📍")]
        except Exception:
            self._world_extra_pts = []

        # Satélites
        CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        names = sorted(self.satellites.keys())
        self._world_sat_pts = []  # Reset tracking for tooltip
        for i, name in enumerate(names):
            if i >= len(CHARS):
                break
            pos = self._sat_position_now(name)
            if pos is None:
                continue
            lat, lon = pos
            sx, sy = self._world_latlon_to_xy(lat, lon, w, h)
            is_horizons = is_horizons_object(name)
            label = "☽" if is_horizons else CHARS[i] if i < len(CHARS) else "?"
            self._world_sat_pts.append((sx, sy, name, label))
            is_sel = (name == self.selected_sat)

            if is_horizons:
                # Orion: amarillo con "H"
                if is_sel:
                    c.create_oval(sx-10, sy-10, sx+10, sy+10,
                                  outline="#c0a000", width=2, fill="")
                c.create_oval(sx-6, sy-6, sx+6, sy+6,
                              fill="#c0a000", outline="#806000")
                c.create_text(sx, sy, text="☽",
                              font=("Courier New", 7, "bold"),
                              fill="#000000")
            elif is_sel:
                # Seleccionado: halo
                c.create_oval(sx-10, sy-10, sx+10, sy+10,
                              outline="#505050", width=1, fill="")
                c.create_oval(sx-6, sy-6, sx+6, sy+6,
                              fill="#606060", outline="")
                c.create_text(sx, sy, text=label,
                              font=("Courier New", 7, "bold"),
                              fill="#202020")
            else:
                c.create_oval(sx-5, sy-5, sx+5, sy+5,
                              fill="#1e1e1e", outline="#404040", width=1)
                c.create_text(sx, sy, text=label,
                              font=("Courier New", 6),
                              fill="#808080")

        # ── Sol y Luna en mapamundi ──
        if EPHEM_OK:
            try:
                _obs_wm = ephem.Observer()
                _obs_wm.lat = str(self.cfg.get("obs_lat", OBS_LAT))
                _obs_wm.lon = str(self.cfg.get("obs_lon", OBS_LON))
                _obs_wm.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
                _obs_wm.date = self._get_now().replace(tzinfo=None)

                # Sol
                _sun_wm = ephem.Sun()
                _sun_wm.compute(_obs_wm)
                sun_lat = float(_sun_wm.dec) * DEG  # subsolar point latitude ~ declination
                # subsolar longitude = RA - GST
                _j2000 = datetime(2000, 1, 1, 12, 0, 0)
                _now_wm = self._get_now().replace(tzinfo=None)
                _d_wm = (_now_wm - _j2000).total_seconds() / 86400.0
                _gst = (280.46061837 + 360.98564736629 * _d_wm) % 360
                sun_lon = (float(_sun_wm.ra) * DEG - _gst) % 360
                if sun_lon > 180:
                    sun_lon -= 360
                sx_sun, sy_sun = self._world_latlon_to_xy(sun_lat, sun_lon, w, h)
                _wm_sun_fill = "#4080c0" if is_horizons_object(self.selected_sat) else "#c0a000"
                _wm_sun_out = "#305080" if is_horizons_object(self.selected_sat) else "#806000"
                c.create_oval(sx_sun-7, sy_sun-7, sx_sun+7, sy_sun+7,
                              fill=_wm_sun_fill, outline=_wm_sun_out, width=1)
                c.create_text(sx_sun, sy_sun, text="\u2600",
                              font=("Courier New", 8, "bold"), fill="#000000")

                # Luna — siempre visible en el mapamundi
                _moon_wm = ephem.Moon()
                _moon_wm.compute(_obs_wm)
                moon_lat = float(_moon_wm.dec) * DEG
                moon_lon = (float(_moon_wm.ra) * DEG - _gst) % 360
                if moon_lon > 180:
                    moon_lon -= 360
                sx_moon, sy_moon = self._world_latlon_to_xy(moon_lat, moon_lon, w, h)
                if is_horizons_object(self.selected_sat):
                    # Gajo de luna menguante: dos curvas cóncavas mirando a la derecha
                    # Dibujado con polígono suave para que quede bonito
                    import math as _m
                    _pts = []
                    _mr = 10
                    # Arco exterior (semicírculo izquierdo completo)
                    for a in range(90, 271, 5):
                        rad = _m.radians(a)
                        _pts.append(sx_moon + _mr * _m.cos(rad))
                        _pts.append(sy_moon - _mr * _m.sin(rad))
                    # Arco interior (curva cóncava, óvalo más estrecho, vuelve arriba)
                    for a in range(270, 89, -5):
                        rad = _m.radians(a)
                        _pts.append(sx_moon + _mr * 0.35 * _m.cos(rad))
                        _pts.append(sy_moon - _mr * _m.sin(rad))
                    c.create_polygon(*_pts, outline="#c0c0c0", fill="",
                                     width=1, smooth=True)
                else:
                    c.create_oval(sx_moon-6, sy_moon-6, sx_moon+6, sy_moon+6,
                                  fill="#707070", outline="#505050", width=1)
                    c.create_text(sx_moon, sy_moon, text="\u263D",
                                  font=("Courier New", 7, "bold"), fill="#000000")
                # Registrar Sol y Luna para tooltip
                self._world_extra_pts.append((sx_sun, sy_sun, f"Sol  {sun_lat:.1f}°N {sun_lon:.1f}°E", "☀"))
                self._world_extra_pts.append((sx_moon, sy_moon, f"Luna  {moon_lat:.1f}°N {moon_lon:.1f}°E", "☽"))
            except Exception:
                pass

    def _on_world_click(self, event):
        """Selecciona un satélite haciendo clic en el mapa mundial."""
        c = self.world_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        names = sorted(self.satellites.keys())
        best_name = None
        best_d = 15
        for name in names:
            pos = self._sat_position_now(name)
            if pos is None:
                continue
            lat, lon = pos
            sx, sy = self._world_latlon_to_xy(lat, lon, w, h)
            d = math.hypot(event.x - sx, event.y - sy)
            if d < best_d:
                best_d = d
                best_name = name
        if best_name:
            # Seleccionar en la listbox principal
            for i in range(self.sat_listbox.size()):
                if self.sat_listbox.get(i) == best_name:
                    self.sat_listbox.selection_clear(0, tk.END)
                    self.sat_listbox.selection_set(i)
                    self.sat_listbox.see(i)
                    self._on_sat_select()
                    break

    def _on_world_motion(self, event):
        """Tooltip al pasar el ratón sobre un satélite del mapa mundial."""
        c = self.world_canvas
        # Borrar tooltip anterior
        if self._world_tooltip:
            c.delete(self._world_tooltip)
            self._world_tooltip = None

        mx, my = event.x, event.y
        best = None
        best_d = 15
        # Buscar en satélites
        for (sx, sy, name, label) in self._world_sat_pts:
            d = math.hypot(mx - sx, my - sy)
            if d < best_d:
                best_d = d
                best = (sx, sy, name, label)
        # Buscar en Sol, Luna, Valencia
        for (sx, sy, name, label) in getattr(self, '_world_extra_pts', []):
            d = math.hypot(mx - sx, my - sy)
            if d < best_d:
                best_d = d
                best = (sx, sy, name, label)

        if best:
            sx, sy, name, label = best
            # Tooltip encima o debajo segun posicion
            ty = sy - 14 if sy > 20 else sy + 14
            tx = sx + 8
            anc = tk.W
            if sx > c.winfo_width() - 100:
                tx = sx - 8
                anc = tk.E
            self._world_tooltip = c.create_text(
                tx, ty,
                text=f"{label}: {name}",
                font=("Courier New", 8, "bold"),
                fill="#e0e0e0",
                anchor=anc,
            )

    def _world_update(self):
        """Actualiza el mapa mundial cada 10 segundos."""
        self._draw_world()
        self.root.after(10000, self._world_update)

    def _build_log_panel(self, parent):
        f = self._panel(parent, "LOG")
        f.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            f, font=("Courier New", 8),
            bg=self.C["grid"], fg=self.C["text"],
            insertbackground=self.C["accent"],
            relief=tk.FLAT, bd=0, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config("ok",   foreground=self.C["green"])
        self.log_text.tag_config("warn", foreground=self.C["yellow"])
        self.log_text.tag_config("err",  foreground=self.C["red"])
        self.log_text.tag_config("info", foreground=self.C["accent"])
        self.log_text.tag_config("data", foreground=self.C["orange"])

        tk.Button(f, text="Limpiar log",
                  command=lambda: self.log_text.delete(1.0, tk.END),
                  font=("Courier New", 8),
                  fg=self.C["muted"], bg=self.C["border"],
                  relief=tk.FLAT, bd=0, pady=2, cursor="hand2").pack(pady=2)

    # ── Pestaña TABLA DE PRÓXIMOS PASOS ─────────────────────

    def _build_table_tab(self, parent):
        # Barra de herramientas de la tabla
        toolbar = tk.Frame(parent, bg=self.C["panel"])
        toolbar.pack(fill=tk.X, padx=6, pady=4)

        tk.Button(toolbar, text="⟳  Calcular todos los pasos (48h)",
                  command=self._calc_all_passes,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["accent"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, padx=12, pady=4,
                  cursor="hand2").pack(side=tk.LEFT, padx=4)

        tk.Button(toolbar, text="▶  Seguir seleccionado",
                  command=self._track_from_table,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["green"], bg=self.C["border"],
                  relief=tk.FLAT, bd=0, padx=12, pady=4,
                  cursor="hand2").pack(side=tk.LEFT, padx=4)

        self.lbl_table_status = tk.Label(toolbar, text="",
                                          font=("Courier New", 8),
                                          fg=self.C["yellow"], bg=self.C["panel"])
        self.lbl_table_status.pack(side=tk.LEFT, padx=8)

        # Filtro elevación mínima
        tk.Label(toolbar, text="El.min:", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["panel"]).pack(side=tk.RIGHT, padx=4)
        self.min_el_var = tk.DoubleVar(value=ELEV_MIN)
        tk.Spinbox(toolbar, from_=0, to=60, increment=5,
                   textvariable=self.min_el_var,
                   font=("Courier New", 8), width=4,
                   bg=self.C["border2"], fg=self.C["text"],
                   relief=tk.FLAT).pack(side=tk.RIGHT, padx=2)

        # Tabla (Treeview)
        cols = ("sat", "hora_subida", "az_subida", "hora_max", "elev_max",
                "hora_bajada", "az_bajada", "duracion", "sentido")
        headers = ("Satélite", "Sube", "Az↑", "Hora max", "El.max",
                   "Baja", "Az↓", "Dur.", "Sentido")
        widths   = (130, 75, 45, 75, 55, 75, 45, 45, 75)

        style = ttk.Style()
        style.configure("Table.Treeview",
                         background="#101010",
                         fieldbackground="#101010",
                         foreground="#f0f0f0",
                         rowheight=22,
                         font=("Courier New", 9))
        style.configure("Table.Treeview.Heading",
                         background="#1a1a1a",
                         foreground="#c0c0c0",
                         font=("Courier New", 9, "bold"),
                         relief=tk.FLAT)
        style.map("Table.Treeview",
                  background=[('selected', '#1a2a3a')],
                  foreground=[('selected', '#ffffff')])

        frame_tree = tk.Frame(parent, bg=self.C["bg"])
        frame_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        vsb = tk.Scrollbar(frame_tree, bg=self.C["border"])
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = tk.Scrollbar(frame_tree, orient=tk.HORIZONTAL, bg=self.C["border"])
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree = ttk.Treeview(frame_tree, columns=cols, show='headings',
                                  style="Table.Treeview",
                                  yscrollcommand=vsb.set,
                                  xscrollcommand=hsb.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        for col, hdr, w in zip(cols, headers, widths):
            self.tree.heading(col, text=hdr,
                              command=lambda c=col: self._sort_table(c))
            self.tree.column(col, width=w, anchor=tk.CENTER, minwidth=w)

        # Tags de color por elevación
        self.tree.tag_configure("high",   foreground="#80e080")
        self.tree.tag_configure("medium", foreground="#e0c060")
        self.tree.tag_configure("low",    foreground="#b0b0b0")
        self.tree.tag_configure("past",   foreground="#505050")

        self.tree.bind('<Double-1>', lambda e: self._track_from_table())

    # ── Pestaña GESTIÓN DE SATÉLITES ────────────────────────

    def _build_sats_tab(self, parent):
        # Panel izquierdo: lista + botones
        left = tk.Frame(parent, bg=self.C["bg"], width=300)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        left.pack_propagate(False)

        right = tk.Frame(parent, bg=self.C["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6), pady=6)

        # Lista de satélites actuales
        f_list = self._panel(left, "MIS SATÉLITES")
        f_list.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        lf = tk.Frame(f_list, bg=self.C["panel"])
        lf.pack(fill=tk.BOTH, expand=True)
        sb2 = tk.Scrollbar(lf)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.manage_listbox = tk.Listbox(
            lf, font=("Courier New", 9),
            bg=self.C["grid"], fg=self.C["text"],
            selectbackground=self.C["accent2"],
            selectforeground="#606060",
            relief=tk.FLAT, bd=0,
            yscrollcommand=sb2.set,
            activestyle='none')
        self.manage_listbox.pack(fill=tk.BOTH, expand=True)
        sb2.config(command=self.manage_listbox.yview)

        # Info del satélite seleccionado en gestión
        self.lbl_manage_info = tk.Label(f_list, text="",
                                         font=("Courier New", 8),
                                         fg=self.C["muted"], bg=self.C["panel"],
                                         justify=tk.LEFT, wraplength=260)
        self.lbl_manage_info.pack(anchor=tk.W, pady=2)
        self.manage_listbox.bind('<<ListboxSelect>>', self._on_manage_select)

        # Botones de gestión
        # Botones con dos solos niveles: normal y acción destacada
        btn_data = [
            ("+  Anadir satelite",           self._add_satellite_dialog, "hi"),
            ("-  Quitar seleccionado",        self._remove_satellite,     "lo"),
            (None, None, None),
            ("v  Actualizar TLEs seleccionados", self._update_selected_tles, "hi"),
            ("vv Actualizar TODOS los TLEs",     self._update_all_tles,      "hi"),
            (None, None, None),
            ("/  Importar archivo .TLE",      self._import_tle_file,      "lo"),
            ("S  Exportar mis satelites",     self._export_tle_file,      "lo"),
        ]

        f_btns = self._panel(left, "ACCIONES")
        f_btns.pack(fill=tk.X)
        for txt, cmd, level in btn_data:
            if cmd is None:
                tk.Frame(f_btns, bg="#1a2540", height=1).pack(fill=tk.X, pady=4)
                continue
            fg = "#707070" if level == "hi" else "#607080"
            bg = "#1a2a3a" if level == "hi" else "#0f1629"
            tk.Button(f_btns, text=txt, command=cmd,
                      font=("Courier New", 9),
                      fg=fg, bg=bg,
                      activeforeground="#606060",
                      activebackground="#243050",
                      relief=tk.FLAT, bd=0,
                      pady=5, padx=6, anchor=tk.W,
                      cursor="hand2").pack(fill=tk.X, pady=1)

        # Panel derecho: añadir satélite
        f_add = self._panel(right, "AÑADIR SATÉLITE")
        f_add.pack(fill=tk.BOTH, expand=True)
        self._build_add_satellite_panel(f_add)

    def _build_add_satellite_panel(self, parent):
        """Panel derecho de la pestaña de gestión para buscar/añadir satélites."""

        # Tabs de búsqueda
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True)

        # Tab: por nombre
        t_name = tk.Frame(nb, bg=self.C["panel"])
        nb.add(t_name, text="  Por nombre  ")
        self._build_search_by_name(t_name)

        # Tab: por NORAD
        t_norad = tk.Frame(nb, bg=self.C["panel"])
        nb.add(t_norad, text="  Por NORAD  ")
        self._build_search_by_norad(t_norad)

        # Tab: por URL
        t_url = tk.Frame(nb, bg=self.C["panel"])
        nb.add(t_url, text="  Desde URL  ")
        self._build_search_by_url(t_url)

        # Tab: TLE manual
        t_manual = tk.Frame(nb, bg=self.C["panel"])
        nb.add(t_manual, text="  TLE manual  ")
        self._build_search_manual(t_manual)

        # Resultados de búsqueda
        f_res = self._panel(parent, "RESULTADOS")
        f_res.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        lf = tk.Frame(f_res, bg=self.C["panel"])
        lf.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(lf)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_listbox = tk.Listbox(
            lf, font=("Courier New", 9),
            bg=self.C["grid"], fg=self.C["text"],
            selectbackground=self.C["accent2"],
            selectforeground="#606060",
            relief=tk.FLAT, bd=0,
            yscrollcommand=sb.set,
            activestyle='none')
        self.search_listbox.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.search_listbox.yview)

        self._search_results = {}   # {nombre: (l1,l2)}

        row = tk.Frame(f_res, bg=self.C["panel"])
        row.pack(fill=tk.X, pady=4)
        tk.Button(row, text="➕  Añadir seleccionado a mis satélites",
                  command=self._add_from_search,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["green"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, pady=4,
                  cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(row, text="➕  Añadir todos",
                  command=self._add_all_from_search,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["yellow"], bg=self.C["border"],
                  relief=tk.FLAT, bd=0, pady=4,
                  cursor="hand2").pack(side=tk.LEFT, padx=4)

    def _build_search_by_name(self, parent):
        tk.Label(parent, text="Nombre del satélite (ej: AO-73, ISS, FUNCUBE):",
                 font=("Courier New", 8), fg=self.C["muted"],
                 bg=self.C["panel"]).pack(anchor=tk.W, padx=8, pady=(8, 2))
        self.name_search_var = tk.StringVar()
        entry = tk.Entry(parent, textvariable=self.name_search_var,
                         font=("Courier New", 10),
                         bg=self.C["border2"], fg=self.C["text"],
                         insertbackground=self.C["accent"],
                         relief=tk.FLAT, bd=4)
        entry.pack(fill=tk.X, padx=8, pady=4)
        entry.bind('<Return>', lambda e: self._search_by_name())
        tk.Button(parent, text="🔍  Buscar en Celestrak",
                  command=self._search_by_name,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["accent"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, pady=4, cursor="hand2").pack(padx=8, pady=4)

    def _build_search_by_norad(self, parent):
        tk.Label(parent, text="Número NORAD (ej: 25544 para ISS):",
                 font=("Courier New", 8), fg=self.C["muted"],
                 bg=self.C["panel"]).pack(anchor=tk.W, padx=8, pady=(8, 2))
        self.norad_search_var = tk.StringVar()
        entry = tk.Entry(parent, textvariable=self.norad_search_var,
                         font=("Courier New", 10),
                         bg=self.C["border2"], fg=self.C["text"],
                         insertbackground=self.C["accent"],
                         relief=tk.FLAT, bd=4)
        entry.pack(fill=tk.X, padx=8, pady=4)
        entry.bind('<Return>', lambda e: self._search_by_norad())
        tk.Button(parent, text="🔍  Buscar por NORAD",
                  command=self._search_by_norad,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["accent"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, pady=4, cursor="hand2").pack(padx=8, pady=4)

    def _build_search_by_url(self, parent):
        tk.Label(parent, text="URL de un archivo TLE (Celestrak, AMSAT, etc.):",
                 font=("Courier New", 8), fg=self.C["muted"],
                 bg=self.C["panel"]).pack(anchor=tk.W, padx=8, pady=(8, 2))
        self.url_search_var = tk.StringVar(value="https://celestrak.org/pub/TLE/amateur.txt")
        entry = tk.Entry(parent, textvariable=self.url_search_var,
                         font=("Courier New", 8),
                         bg=self.C["border2"], fg=self.C["text"],
                         insertbackground=self.C["accent"],
                         relief=tk.FLAT, bd=4)
        entry.pack(fill=tk.X, padx=8, pady=4)

        # URLs predefinidas
        tk.Label(parent, text="URLs predefinidas:",
                 font=("Courier New", 8), fg=self.C["muted"],
                 bg=self.C["panel"]).pack(anchor=tk.W, padx=8)
        for name, url in CELESTRAK_GROUPS.items():
            tk.Button(parent, text=f"  {name}",
                      command=lambda u=url: self.url_search_var.set(u),
                      font=("Courier New", 8),
                      fg=self.C["muted"], bg=self.C["panel"],
                      relief=tk.FLAT, bd=0, anchor=tk.W,
                      cursor="hand2").pack(fill=tk.X, padx=8)

        tk.Button(parent, text="⬇  Descargar desde URL",
                  command=self._search_by_url,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["accent"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, pady=4, cursor="hand2").pack(padx=8, pady=8)

    def _build_search_manual(self, parent):
        tk.Label(parent, text="Pega las 3 líneas TLE directamente:",
                 font=("Courier New", 8), fg=self.C["muted"],
                 bg=self.C["panel"]).pack(anchor=tk.W, padx=8, pady=(8, 2))
        self.manual_tle_text = tk.Text(parent, height=6,
                                        font=("Courier New", 9),
                                        bg=self.C["border2"], fg=self.C["text"],
                                        insertbackground=self.C["accent"],
                                        relief=tk.FLAT, bd=4)
        self.manual_tle_text.pack(fill=tk.X, padx=8, pady=4)
        self.manual_tle_text.insert(tk.END,
            "NOMBRE DEL SATELITE\n"
            "1 XXXXXU XXXXXXXX XXXXX.XXXXXXXX  .XXXXXXXX  XXXXX-X XXXXX-X X XXXXX\n"
            "2 XXXXX XXX.XXXX XXX.XXXX XXXXXXX XXX.XXXX XXX.XXXX XX.XXXXXXXXXXXXXXXXX")
        tk.Button(parent, text="✔  Añadir este TLE",
                  command=self._add_manual_tle,
                  font=("Courier New", 9, "bold"),
                  fg=self.C["green"], bg=self.C["border2"],
                  relief=tk.FLAT, bd=0, pady=4, cursor="hand2").pack(padx=8, pady=4)

    # ── Pestaña CONFIGURACIÓN ────────────────────────────────

    def _build_config_tab(self, parent):
        # ── Indicativo y zona horaria ──
        f0 = self._panel(parent, "ESTACIÓN")
        f0.pack(fill=tk.X, padx=12, pady=(12,4))

        row0 = tk.Frame(f0, bg=self.C["panel"])
        row0.pack(fill=tk.X, pady=2)
        tk.Label(row0, text="Indicativo:",
                 font=("Courier New", 9), fg=self.C["muted"],
                 bg=self.C["panel"], width=16).pack(side=tk.LEFT)
        self._call_var = tk.StringVar(value=self.cfg.get("callsign", ""))
        tk.Entry(row0, textvariable=self._call_var,
                 font=("Courier New", 10, "bold"),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"],
                 relief=tk.FLAT, bd=3, width=12).pack(side=tk.LEFT)

        row_tz = tk.Frame(f0, bg=self.C["panel"])
        row_tz.pack(fill=tk.X, pady=6)
        tk.Label(row_tz, text="Horas:",
                 font=("Courier New", 9), fg=self.C["muted"],
                 bg=self.C["panel"], width=16).pack(side=tk.LEFT)
        self._utc_var = tk.BooleanVar(value=self.cfg.get("use_utc", True))
        tk.Radiobutton(row_tz, text="UTC",
                       variable=self._utc_var, value=True,
                       font=("Courier New", 9, "bold"),
                       fg=self.C["text"], bg=self.C["panel"],
                       selectcolor=self.C["bg"],
                       activebackground=self.C["panel"]).pack(side=tk.LEFT, padx=4)
        tk.Radiobutton(row_tz, text="Local",
                       variable=self._utc_var, value=False,
                       font=("Courier New", 9),
                       fg=self.C["text"], bg=self.C["panel"],
                       selectcolor=self.C["bg"],
                       activebackground=self.C["panel"]).pack(side=tk.LEFT, padx=4)
        self.lbl_tz_hint = tk.Label(row_tz, text="",
                                     font=("Courier New", 8),
                                     fg=self.C["muted"], bg=self.C["panel"])
        self.lbl_tz_hint.pack(side=tk.LEFT, padx=8)
        self._utc_var.trace_add('write', self._on_tz_change)
        self._on_tz_change()

        # ── Observador ──
        f = self._panel(parent, "OBSERVADOR")
        f.pack(fill=tk.X, padx=12, pady=4)

        fields = [
            ("Latitud (+N):",   "obs_lat",  OBS_LAT),
            ("Longitud (+E):",  "obs_lon",  OBS_LON),
            ("Elevación (m):",  "obs_elev", str(OBS_ELEV)),
        ]
        self._obs_vars = {}
        for label, key, default in fields:
            row = tk.Frame(f, bg=self.C["panel"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=("Courier New", 9),
                     fg=self.C["muted"], bg=self.C["panel"], width=16).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(self.cfg.get(key, default)))
            tk.Entry(row, textvariable=var, font=("Courier New", 9),
                     bg=self.C["border2"], fg=self.C["text"],
                     insertbackground=self.C["accent"],
                     relief=tk.FLAT, bd=3, width=18).pack(side=tk.LEFT)
            self._obs_vars[key] = var

        # Campo Lugar (nombre para el mapamundi)
        row_name = tk.Frame(f, bg=self.C["panel"])
        row_name.pack(fill=tk.X, pady=2)
        tk.Label(row_name, text="Lugar:", font=("Courier New", 9),
                 fg=self.C["muted"], bg=self.C["panel"], width=16).pack(side=tk.LEFT)
        self._obs_name_var = tk.StringVar(value=self.cfg.get("obs_name", ""))
        tk.Entry(row_name, textvariable=self._obs_name_var, font=("Courier New", 9),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"],
                 relief=tk.FLAT, bd=3, width=18).pack(side=tk.LEFT)

        # Campo Locator (Maidenhead)
        row_loc = tk.Frame(f, bg=self.C["panel"])
        row_loc.pack(fill=tk.X, pady=2)
        tk.Label(row_loc, text="Locator:", font=("Courier New", 9),
                 fg=self.C["muted"], bg=self.C["panel"], width=16).pack(side=tk.LEFT)
        self._locator_var = tk.StringVar(value=latlon_to_locator(
            self.cfg.get("obs_lat", OBS_LAT), self.cfg.get("obs_lon", OBS_LON)))
        tk.Entry(row_loc, textvariable=self._locator_var, font=("Courier New", 9),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"],
                 relief=tk.FLAT, bd=3, width=18).pack(side=tk.LEFT)

        # Botones: Locator→LatLon y LatLon→Locator
        btn_row = tk.Frame(f, bg=self.C["panel"])
        btn_row.pack(fill=tk.X, pady=2)
        tk.Button(btn_row, text="Locator → Lat/Lon",
                  command=self._locator_to_latlon,
                  font=("Courier New", 8),
                  fg="#505050", bg="#121212",
                  relief=tk.FLAT, bd=0, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Lat/Lon → Locator",
                  command=self._latlon_to_locator,
                  font=("Courier New", 8),
                  fg="#505050", bg="#121212",
                  relief=tk.FLAT, bd=0, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=4)

        tk.Button(f, text="Guardar",
                  command=self._save_observer,
                  font=("Courier New", 9, "bold"),
                  fg="#505050", bg="#121212",
                  relief=tk.FLAT, bd=0, pady=4, cursor="hand2").pack(pady=6)

        # ── Simulador de hora (para pruebas) ──
        f_sim = self._panel(parent, "SIMULADOR DE HORA")
        f_sim.pack(fill=tk.X, padx=12, pady=4)

        row_sim_en = tk.Frame(f_sim, bg=self.C["panel"])
        row_sim_en.pack(fill=tk.X, pady=2)
        self._sim_enabled = tk.BooleanVar(value=False)
        tk.Checkbutton(row_sim_en, text="Activar hora manual",
                       variable=self._sim_enabled,
                       font=("Courier New", 9),
                       fg=self.C["text"], bg=self.C["panel"],
                       selectcolor=self.C["bg"],
                       activebackground=self.C["panel"],
                       command=self._on_sim_toggle).pack(side=tk.LEFT)

        row_sim_dt = tk.Frame(f_sim, bg=self.C["panel"])
        row_sim_dt.pack(fill=tk.X, pady=2)
        tk.Label(row_sim_dt, text="Fecha (DD/MM/AAAA):", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["panel"]).pack(side=tk.LEFT)
        self._sim_date_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        tk.Entry(row_sim_dt, textvariable=self._sim_date_var, font=("Courier New", 9),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"],
                 relief=tk.FLAT, bd=3, width=12).pack(side=tk.LEFT, padx=4)

        row_sim_tm = tk.Frame(f_sim, bg=self.C["panel"])
        row_sim_tm.pack(fill=tk.X, pady=2)
        _tz_hint = "UTC" if self.cfg.get("use_utc", True) else "LOCAL"
        self._sim_tz_label = tk.Label(row_sim_tm, text=f"Hora (HH:MM) {_tz_hint}:",
                 font=("Courier New", 8), fg=self.C["muted"], bg=self.C["panel"])
        self._sim_tz_label.pack(side=tk.LEFT)
        self._sim_time_var = tk.StringVar(value=datetime.now(timezone.utc).strftime("%H:%M"))
        tk.Entry(row_sim_tm, textvariable=self._sim_time_var, font=("Courier New", 9),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"],
                 relief=tk.FLAT, bd=3, width=8).pack(side=tk.LEFT, padx=4)

        tk.Button(f_sim, text="Aplicar hora",
                  command=self._apply_sim_time,
                  font=("Courier New", 8),
                  fg="#505050", bg="#121212",
                  relief=tk.FLAT, bd=0, pady=2, cursor="hand2").pack(pady=4)

        # Info
        f2 = self._panel(parent, "INFORMACIÓN")
        f2.pack(fill=tk.X, padx=12)
        info = (f"Versión: {APP_VERSION}\n"
                f"Config: {CONFIG_FILE}\n"
                f"TLE: {TLE_FILE.resolve()}\n"
                f"ephem: {'OK' if EPHEM_OK else 'NO INSTALADO'}\n"
                f"pyserial: {'OK' if SERIAL_OK else 'NO INSTALADO'}")
        tk.Label(f2, text=info, font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["panel"],
                 justify=tk.LEFT).pack(anchor=tk.W)

    def _get_now(self):
        """Devuelve datetime UTC — hora real o simulada según configuración."""
        if hasattr(self, '_sim_enabled') and self._sim_enabled.get() and hasattr(self, '_sim_datetime'):
            return self._sim_datetime
        return datetime.now(timezone.utc)

    def _on_sim_toggle(self):
        if self._sim_enabled.get():
            self._apply_sim_time()
            self.log("Simulador de hora ACTIVADO", "warn")
        else:
            if hasattr(self, '_sim_datetime'):
                del self._sim_datetime
            self.log("Simulador de hora DESACTIVADO — usando hora real", "ok")
            # Reinicializar TODOS los datos con hora real
            self._reinit_all_tracks()

    def _apply_sim_time(self):
        try:
            date_str = self._sim_date_var.get().strip()
            time_str = self._sim_time_var.get().strip()
            parts_d = date_str.split("/")
            parts_t = time_str.split(":")
            if self.cfg.get("use_utc", True):
                # El usuario introduce UTC
                self._sim_datetime = datetime(
                    int(parts_d[2]), int(parts_d[1]), int(parts_d[0]),
                    int(parts_t[0]), int(parts_t[1]), 0,
                    tzinfo=timezone.utc)
            else:
                # El usuario introduce hora LOCAL — convertir a UTC
                from datetime import timezone as _tz
                _local_dt = datetime(
                    int(parts_d[2]), int(parts_d[1]), int(parts_d[0]),
                    int(parts_t[0]), int(parts_t[1]), 0)
                _local_dt = _local_dt.astimezone()  # añade zona local
                self._sim_datetime = _local_dt.astimezone(timezone.utc)
            self.log(f"Hora simulada: {self._sim_datetime.strftime('%d/%m/%Y %H:%M')} UTC", "ok")
            # Reinicializar TODOS los datos con hora simulada
            self._reinit_all_tracks()
        except Exception as e:
            self.log(f"Error en fecha/hora: {e}", "err")

    def _reinit_all_tracks(self):
        """Reinicializa TODOS los datos de órbitas y trayectorias.
        Se llama al cambiar entre hora manual/automática o al cambiar la hora."""
        # Limpiar datos anteriores
        self.sun_track = []
        self.moon_track = []
        self._sun_screen_pts = []
        self._moon_screen_pts = []
        # Recalcular Sol/Luna
        threading.Thread(target=self._calculate_sun_moon_tracks, daemon=True).start()
        # Recalcular pases del satélite seleccionado
        if self.selected_sat:
            if is_horizons_object(self.selected_sat):
                self.future_track = []
                self.pass_track = []
                threading.Thread(target=self._load_horizons_pass, daemon=True).start()
            elif EPHEM_OK and self.selected_sat in self.satellites:
                self.future_track = []
                self.pass_track = []
                self.sat_passes = []
                self.pass_index = 0
                threading.Thread(target=self._load_sat_passes, daemon=True).start()
        # Redibujar inmediatamente (limpio)
        self._draw_polar()
        self._draw_world()

    def _on_tz_change(self, *_):
        """Actualiza el hint de zona horaria y la barra superior."""
        use_utc = self._utc_var.get()
        import time as _time
        local_name = _time.strftime("%Z")
        if use_utc:
            self.lbl_tz_hint.config(text="(horas en UTC)")
        else:
            self.lbl_tz_hint.config(text=f"(horas en {local_name})")
        self.cfg["use_utc"] = use_utc
        save_config(self.cfg)
        self._draw_polar()

    # ── Utilidades UI ────────────────────────────────────────

    def _panel(self, parent, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=self.C["border"], padx=1, pady=1)
        outer.pack(fill=tk.X, padx=6, pady=3)
        inner = tk.Frame(outer, bg=self.C["panel"], padx=8, pady=6)
        inner.pack(fill=tk.BOTH, expand=True)
        tk.Label(inner, text=title, font=("Courier New", 7, "bold"),
                 fg=self.C["accent"], bg=self.C["panel"]).pack(anchor=tk.W, pady=(0, 3))
        return inner

    def log(self, msg: str, tag: str = "info"):
        _now = self._get_now()
        if self.cfg.get("use_utc", True):
            ts = _now.strftime("%H:%M:%S")
        else:
            ts = _now.astimezone().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self.log_text.see(tk.END)

    def _tick_clock(self):
        _now = self._get_now()
        _is_sim = hasattr(self, '_sim_enabled') and self._sim_enabled.get()
        _prefix = "SIM" if _is_sim else ("UTC" if self.cfg.get("use_utc", True) else "LOC")
        if self.cfg.get("use_utc", True):
            now = f"{_prefix}  {_now.strftime('%Y-%m-%d  %H:%M:%S')}"
        else:
            now = f"{_prefix}  {_now.astimezone().strftime('%Y-%m-%d  %H:%M:%S')}"
        self.lbl_time.config(text=now)

        # Refresco periódico de trayectoria Horizons (cada 30 min)
        import time as _time
        if (self.selected_sat and is_horizons_object(self.selected_sat)
                and self.tracking
                and _time.time() - self._last_track_refresh > 600):
            self._last_track_refresh = _time.time()
            self.log("Refrescando datos Horizons...", "info")
            threading.Thread(target=self._load_horizons_pass, daemon=True).start()
            threading.Thread(target=self._calculate_sun_moon_tracks, daemon=True).start()

        # Auto-refresh Horizons cada 10 min si Orion seleccionado
        import time as _t
        if (self.selected_sat and is_horizons_object(self.selected_sat)
                and not self.tracking
                and _t.time() - self._last_horizons_refresh > 600):
            self._last_horizons_refresh = _t.time()
            self.log("Auto-refresh: actualizando todo...", "info")
            threading.Thread(target=self._load_horizons_pass, daemon=True).start()
            threading.Thread(target=self._calculate_sun_moon_tracks, daemon=True).start()

        self.root.after(1000, self._tick_clock)

    def _tick_orion_moon_toggle(self):
        """Desactivada — ambas trayectorias siempre visibles."""
        self.root.after(4000, self._tick_orion_moon_toggle)

    def _calculate_sun_moon_tracks(self):
        """Calcula trayectorias 24h de Sol y Luna con ephem (para todos los satélites)."""
        if not EPHEM_OK:
            return
        try:
            sun_obj = ephem.Sun()
            moon_obj = ephem.Moon()
            obs = ephem.Observer()
            obs.lat = str(self.cfg.get("obs_lat", OBS_LAT))
            obs.lon = str(self.cfg.get("obs_lon", OBS_LON))
            obs.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
            now = self._get_now()

            # Primero calcular rise/set precisos para saber desde cuándo
            # generar datos (cubriendo el arco completo desde rise)
            obs.date = now.strftime("%Y/%m/%d %H:%M:%S")
            sun_obj.compute(obs)
            sun_above = float(sun_obj.alt) > 0
            try:
                if sun_above:
                    sun_rise = ephem.Date(obs.previous_rising(ephem.Sun())).datetime().replace(tzinfo=timezone.utc)
                    sun_set = ephem.Date(obs.next_setting(ephem.Sun())).datetime().replace(tzinfo=timezone.utc)
                else:
                    sun_rise = ephem.Date(obs.next_rising(ephem.Sun())).datetime().replace(tzinfo=timezone.utc)
                    obs.date = sun_rise.strftime("%Y/%m/%d %H:%M:%S")
                    sun_set = ephem.Date(obs.next_setting(ephem.Sun())).datetime().replace(tzinfo=timezone.utc)
            except Exception:
                sun_rise = sun_set = None

            obs.date = now.strftime("%Y/%m/%d %H:%M:%S")
            moon_obj.compute(obs)
            moon_above = float(moon_obj.alt) > 0
            try:
                if moon_above:
                    moon_rise = ephem.Date(obs.previous_rising(ephem.Moon())).datetime().replace(tzinfo=timezone.utc)
                    moon_set = ephem.Date(obs.next_setting(ephem.Moon())).datetime().replace(tzinfo=timezone.utc)
                else:
                    moon_rise = ephem.Date(obs.next_rising(ephem.Moon())).datetime().replace(tzinfo=timezone.utc)
                    obs.date = moon_rise.strftime("%Y/%m/%d %H:%M:%S")
                    moon_set = ephem.Date(obs.next_setting(ephem.Moon())).datetime().replace(tzinfo=timezone.utc)
            except Exception:
                moon_rise = moon_set = None

            # Generar datos de rise a set — con punto horizonte al inicio y final
            sun_points = []
            if sun_rise and sun_set:
                # Punto exacto del horizonte al inicio
                obs.date = sun_rise.strftime("%Y/%m/%d %H:%M:%S")
                sun_obj.compute(obs)
                sun_points.append((float(sun_obj.az)*DEG, 0.0,
                                   sun_rise.strftime("%Y-%b-%d %H:%M")))
                # Datos cada 5 min
                _s0 = sun_rise + timedelta(minutes=5)
                _s1 = sun_set - timedelta(minutes=5)
                _sn = int((_s1 - _s0).total_seconds() / 300) + 1
                for i in range(max(0, _sn)):
                    t = _s0 + timedelta(minutes=i * 5)
                    obs.date = t.strftime("%Y/%m/%d %H:%M:%S")
                    sun_obj.compute(obs)
                    el = float(sun_obj.alt) * DEG
                    if el > 0:
                        sun_points.append((float(sun_obj.az)*DEG, el,
                                           t.strftime("%Y-%b-%d %H:%M")))
                # Punto exacto del horizonte al final
                obs.date = sun_set.strftime("%Y/%m/%d %H:%M:%S")
                sun_obj.compute(obs)
                sun_points.append((float(sun_obj.az)*DEG, 0.0,
                                   sun_set.strftime("%Y-%b-%d %H:%M")))

            moon_points = []
            if moon_rise and moon_set:
                # Punto exacto del horizonte al inicio
                obs.date = moon_rise.strftime("%Y/%m/%d %H:%M:%S")
                moon_obj.compute(obs)
                moon_points.append((float(moon_obj.az)*DEG, 0.0,
                                    moon_rise.strftime("%Y-%b-%d %H:%M")))
                # Datos cada 5 min
                _m0 = moon_rise + timedelta(minutes=5)
                _m1 = moon_set - timedelta(minutes=5)
                _mn = int((_m1 - _m0).total_seconds() / 300) + 1
                for i in range(max(0, _mn)):
                    t = _m0 + timedelta(minutes=i * 5)
                    obs.date = t.strftime("%Y/%m/%d %H:%M:%S")
                    moon_obj.compute(obs)
                    el = float(moon_obj.alt) * DEG
                    if el > 0:
                        moon_points.append((float(moon_obj.az)*DEG, el,
                                            t.strftime("%Y-%b-%d %H:%M")))
                # Punto exacto del horizonte al final
                obs.date = moon_set.strftime("%Y/%m/%d %H:%M:%S")
                moon_obj.compute(obs)
                moon_points.append((float(moon_obj.az)*DEG, 0.0,
                                    moon_set.strftime("%Y-%b-%d %H:%M")))

            self.sun_track = sun_points
            self._sun_rise_utc = sun_rise
            self._sun_set_utc = sun_set

            self.moon_track = moon_points
            self.moon_rise_utc = moon_rise
            self.moon_set_utc = moon_set

            self.root.after(0, self._draw_polar)
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Error calculando Sol/Luna: {e}", "err"))

    def _get_orion_subpoint(self):
        """Obtiene sub-punto de Orion (lat/lon) desde Horizons via RA/DEC."""
        try:
            now = self._get_now()
            start = now.strftime("%Y-%m-%d %H:%M")
            stop = (now + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
            body = (
                f"format=json"
                f"&COMMAND='-1024'"
                f"&OBJ_DATA=NO"
                f"&MAKE_EPHEM=YES"
                f"&EPHEM_TYPE=OBSERVER"
                f"&CENTER='coord@399'"
                f"&COORD_TYPE=GEODETIC"
                f"&SITE_COORD='{float(self.cfg.get('obs_lon', OBS_LON))},"
                f"{float(self.cfg.get('obs_lat', OBS_LAT))},"
                f"{float(self.cfg.get('obs_elev', OBS_ELEV))/1000.0}'"
                f"&START_TIME='{start}'"
                f"&STOP_TIME='{stop}'"
                f"&STEP_SIZE='1 m'"
                f"&QUANTITIES='1'"
                f"&ANG_FORMAT=DEG"
                f"&TIME_ZONE='+00:00'"
            )
            req = urllib.request.Request(
                HORIZONS_URL, data=body.encode(),
                headers={'User-Agent': 'EyebitTracker/1.4'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
            result = data.get("result", "")
            in_data = False
            for line in result.split("\n"):
                if "$$SOE" in line: in_data = True; continue
                if "$$EOE" in line: break
                if in_data and line.strip():
                    parts = line.split()
                    if len(parts) >= 5:
                        ra = float(parts[3])
                        dec = float(parts[4])
                        # Sub-punto: DEC=lat, RA-GST=lon
                        j2000 = datetime(2000, 1, 1, 12, 0, 0)
                        d = (now.replace(tzinfo=None) - j2000).total_seconds() / 86400.0
                        gst = (280.46061837 + 360.98564736629 * d) % 360
                        lon = (ra - gst) % 360
                        if lon > 180: lon -= 360
                        return (dec, lon)
        except Exception:
            pass
        return None

    def _tick_auto_position(self):
        """Actualiza posicion del satelite seleccionado cada 2s sin tracking."""
        import time as _t
        if self.selected_sat and not self.tracking:
            try:
                if is_horizons_object(self.selected_sat):
                    # Orion: consultar Horizons cada 30s (es lento)
                    if _t.time() - self._last_auto_fetch > 300:  # cada 5 min
                        self._last_auto_fetch = _t.time()
                        def _fetch():
                            pos = get_horizons_azel(
                                self.selected_sat,
                                self.cfg.get("obs_lat", OBS_LAT),
                                self.cfg.get("obs_lon", OBS_LON),
                                int(self.cfg.get("obs_elev", OBS_ELEV)))
                            # Tambien pedir RA/DEC para sub-punto en mapamundi
                            subpoint = self._get_orion_subpoint()
                            if pos:
                                def _upd():
                                    self.az_now = pos["az"]
                                    self.el_now = pos["el"]
                                    if subpoint:
                                        self._orion_subpoint = subpoint
                                    self._draw_polar()
                                self.root.after(0, _upd)
                        threading.Thread(target=_fetch, daemon=True).start()
                elif EPHEM_OK and self.selected_sat in self.satellites:
                    # Satelites normales: calcular con ephem (rapido)
                    sat = ephem.readtle(self.selected_sat, *self.satellites[self.selected_sat])
                    obs = self._make_observer()
                    obs.date = self._get_now().replace(tzinfo=None)
                    sat.compute(obs)
                    az_new = float(sat.az) * DEG
                    el_new = float(sat.alt) * DEG
                    if abs(az_new - self.az_now) > 0.1 or abs(el_new - self.el_now) > 0.1:
                        self.az_now = az_new
                        self.el_now = el_new
                        self._draw_polar()
            except Exception:
                pass
        self.root.after(2000, self._tick_auto_position)

    def fmt_time(self, dt) -> str:
        """Formatea fecha+hora según preferencia UTC/local.
        dt debe ser datetime UTC aware (timezone.utc)."""
        if self.cfg.get("use_utc", True):
            return dt.strftime("%d/%m %H:%M")
        else:
            return dt.astimezone().strftime("%d/%m %H:%M")

    def fmt_hms(self, dt) -> str:
        """Formatea hora:min:seg según preferencia UTC/local."""
        if self.cfg.get("use_utc", True):
            return dt.strftime("%H:%M:%S")
        else:
            return dt.astimezone().strftime("%H:%M:%S")

    # ── Carga y guardado de satélites ────────────────────────

    def _load_satellites(self):
        """Carga satélites desde archivo local o fallback."""
        if TLE_FILE.exists():
            text = TLE_FILE.read_text(encoding='utf-8')
            self.satellites = parse_tle_text(text)
            self.log(f"Cargados {len(self.satellites)} satélites de {TLE_FILE}", "ok")
        else:
            self.satellites = parse_tle_text(FALLBACK_TLES)
            self.log(f"Usando {len(self.satellites)} satélites de reserva", "warn")
            self._save_satellites()

        # Añadir naves deep-space (Horizons) a la lista
        for name, hid in HORIZONS_OBJECTS.items():
            if name not in self.satellites:
                self.satellites[name] = ("HORIZONS", hid)
        self.log(f"+ {len(HORIZONS_OBJECTS)} naves deep-space (JPL Horizons)", "ok")

        self._populate_all_lists()
        if not EPHEM_OK:
            self.log("⚠  ephem no instalado  →  pip install ephem", "err")
        if not SERIAL_OK:
            self.log("⚠  pyserial no instalado  →  pip install pyserial", "warn")

    def _save_satellites(self):
        tle_only = {k: v for k, v in self.satellites.items() if v[0] != "HORIZONS"}
        save_tle_file(tle_only, TLE_FILE)

    def _auto_update_tles_startup(self):
        """Actualiza TLEs de Celestrak al arrancar (hilo separado)."""
        tle_names = [name for name in self.satellites.keys() if not is_horizons_object(name)]
        if tle_names:
            self.log("Actualizando TLEs desde Celestrak...", "info")
            threading.Thread(target=self._update_tles_worker, args=(tle_names,), daemon=True).start()

    def _populate_all_lists(self):
        """Rellena la listbox de seguimiento y la de gestión."""
        self._filter_listbox()
        self.manage_listbox.delete(0, tk.END)
        for name in sorted(self.satellites.keys()):
            self.manage_listbox.insert(tk.END, name)

    def _filter_listbox(self):
        q = self.search_var.get().upper()
        self.sat_listbox.delete(0, tk.END)
        for name in sorted(self.satellites.keys()):
            if q in name.upper():
                self.sat_listbox.insert(tk.END, name)

    # ── Selección de satélite ────────────────────────────────

    def _on_sat_select(self, event=None):
        sel = self.sat_listbox.curselection()
        if sel:
            self.selected_sat = self.sat_listbox.get(sel[0])
            l1, l2 = self.satellites[self.selected_sat]
            norad = get_norad_from_tle_line(l1)
            self.lbl_sat_info.config(
                text=f"NORAD: {norad}\n{l1[:30]}...",
                fg=self.C["accent"])
            self.pass_track   = []
            self.future_track = []
            self.sat_passes   = []
            self.pass_index   = 0
            self.sentido      = ""
            self.az_now       = 0.0
            self.el_now       = -90.0  # bajo horizonte — no dibuja punto
            self.lbl_pass_counter.config(text="")
            self._draw_polar()
            # Detectar si es objeto Horizons (Orion, deep space)
            if is_horizons_object(self.selected_sat):
                self.log(f"Seleccionado: {self.selected_sat}  🌙 CISLUNAR", "ok")
                self.log("  AVISO: Orion NO se calcula localmente como los satélites.", "warn")
                self.log("  Se conecta por INTERNET a la API de NASA JPL Horizons:", "warn")
                self.log("  https://ssd.jpl.nasa.gov/api/horizons.api", "warn")
                self.log("  Motivo: trayectoria cislunar, no se puede calcular con TLEs.", "info")
                self.log("  Descargando posición y trayectoria de la Luna...", "info")
                self.lbl_sat_info.config(
                    text=f"🌙 CISLUNAR\nNASA Horizons API\nCalculando pase...",
                    fg=self.C["yellow"])
                self.btn_track.config(text="⏳ Descargando...", state=tk.DISABLED)
                threading.Thread(target=self._load_horizons_pass, daemon=True).start()
                # Calcular Sol y Luna para todos los satélites
                threading.Thread(target=self._calculate_sun_moon_tracks, daemon=True).start()
            else:
                self.log(f"Seleccionado: {self.selected_sat}  (NORAD {norad})", "info")
                # Calcular pases automáticamente (solo satélites TLE)
                if EPHEM_OK:
                    threading.Thread(target=self._load_sat_passes, daemon=True).start()
                # Calcular Sol y Luna para todos los satélites
                threading.Thread(target=self._calculate_sun_moon_tracks, daemon=True).start()

    def _on_manage_select(self, event=None):
        sel = self.manage_listbox.curselection()
        if sel:
            name = self.manage_listbox.get(sel[0])
            l1, l2 = self.satellites[name]
            norad = get_norad_from_tle_line(l1)
            self.lbl_manage_info.config(
                text=f"{name}\nNORAD: {norad}\n{l1}\n{l2}",
                fg=self.C["text"])

    # ── Puerto serie ─────────────────────────────────────────

    def _refresh_ports(self):
        if not SERIAL_OK:
            self.port_combo['values'] = ["pyserial no instalado"]
            return
        ports = [p.device for p in serial.tools.list_ports.comports()]
        ports.sort(key=lambda p: (0 if any(x in p for x in
                                            ['CH341', 'usb', 'USB', 'Repleo', 'SLAB']) else 1))
        self.port_combo['values'] = ports if ports else ["(ninguno detectado)"]
        saved = self.cfg.get("serial_port", "")
        if saved and saved in ports:
            self.port_var.set(saved)
        elif ports:
            self.port_combo.current(0)

    def _try_serial_connect(self):
        """Intenta conectar al puerto guardado en config."""
        saved = self.cfg.get("serial_port", "")
        if not saved or not SERIAL_OK:
            return
        # Verificar que el puerto existe
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if saved in ports:
            self.port_var.set(saved)
            self._connect_serial(saved, int(self.baud_var.get()))
        else:
            self.log(f"Puerto guardado '{saved}' no encontrado, buscando alternativo...", "warn")
            # Buscar CH341 u otro USB
            for p in ports:
                if any(x in p for x in ['CH341', 'usb', 'USB', 'Repleo', 'SLAB']):
                    self.port_var.set(p)
                    self.log(f"Puerto alternativo encontrado: {p}", "ok")
                    self._connect_serial(p, int(self.baud_var.get()))
                    return

    def _connect_serial(self, port: str, baud: int):
        try:
            self.serial_conn = serial.Serial(port=port, baudrate=baud, timeout=1)
            self._set_serial_ui(True, port, baud)
            self.log(f"✓ Conectado a {port} @ {baud}", "ok")
            self.cfg["serial_port"] = port
            self.cfg["serial_baud"] = baud
            save_config(self.cfg)
        except Exception as e:
            self.log(f"Error al conectar {port}: {e}", "err")

    def _toggle_serial(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.serial_conn = None
            self._set_serial_ui(False)
            self.log("Puerto serie desconectado", "warn")
        else:
            if not SERIAL_OK:
                self.log("Instala pyserial: pip install pyserial", "err")
                return
            port = self.port_var.get()
            baud = int(self.baud_var.get())
            self._connect_serial(port, baud)

    def _set_serial_ui(self, connected: bool, port: str = "", baud: int = 0):
        if connected:
            txt = f"● {port} @ {baud}"
            color = self.C["green"]
            btxt  = "DESCONECTAR"
        else:
            txt   = "● Desconectado"
            color = self.C["red"]
            btxt  = "CONECTAR"
        self.lbl_serial.config(text=txt, fg=color)
        self.lbl_serial_top.config(text=txt, fg=color)
        self.btn_serial.config(text=btxt)

    def _send_serial(self, az_motor: float, el_motor: float):
        """Envía 'az,el' al ESP32 por el puerto serie."""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                data = f"{int(round(az_motor))},{int(round(el_motor))}"
                self.serial_conn.write(data.encode())
                self.log(f"→ ESP32: AZ={int(az_motor)}°  EL={int(el_motor)}°", "data")
            except Exception as e:
                self.log(f"Error serial: {e}", "err")
        else:
            self.log(f"[Sin ESP32] AZ_motor={int(az_motor)}°  EL={int(el_motor)}°", "warn")

    # ── Seguimiento Horizons (Orion / deep space) ───────────

    def _track_loop_horizons(self):
        """Bucle de seguimiento para objetos cislunar/deep space via NASA Horizons."""
        global syncan_mount
        sat_name = self.selected_sat
        interval = self.interval_var.get()
        if interval < 5:
            interval = 10  # Horizons no necesita más de 1 consulta cada 10s

        self.root.after(0, lambda: self.log(
            "Conectando con NASA Horizons...", "info"))

        fail_count = 0
        while self.tracking and self.selected_sat == sat_name:
            pos = get_horizons_azel(
                sat_name,
                self.cfg.get("obs_lat", OBS_LAT),
                self.cfg.get("obs_lon", OBS_LON),
                int(self.cfg.get("obs_elev", OBS_ELEV))
            )

            if pos is None:
                fail_count += 1
                if fail_count >= 5:
                    self.root.after(0, lambda: self.log(
                        "CONEXION PERDIDA — reintentar?", "err"))
                    self.tracking = False
                    break
                self.root.after(0, lambda: self.log(
                    "Error consultando Horizons, reintentando...", "err"))
                time.sleep(10)
                continue

            fail_count = 0
            az = pos["az"]
            el = pos["el"]
            dist_km = pos["dist_km"]

            self.az_now = az
            self.el_now = el

            # Distancia legible
            if dist_km > 1e6:
                dist_str = f"{dist_km/1e6:.1f}M km"
            else:
                dist_str = f"{dist_km:,.0f} km"

            # Enviar a montura AZ-GTiX si conectada
            if syncan_mount and syncan_mount.connected and el > 0:
                syncan_mount.goto_azalt(az, el)
                mount_str = f"→ Montura AZ={az:.1f}° EL={el:.1f}°"
            elif syncan_mount and syncan_mount.connected and el <= 0:
                mount_str = "Bajo horizonte — montura en espera"
            else:
                mount_str = ""

            # Enviar a ESP32 serial si conectado (az directo, no servo)
            if el > 0:
                self._send_serial(az, el)
                self.pass_track.append((az, el))

            # Actualizar GUI
            visible = el > 0
            def _upd(az=az, el=el, dist_str=dist_str, vis=visible, ms=mount_str):
                self._telem_labels["lbl_az"].config(
                    text=f"{az:.2f}°", fg=self.C["accent"])
                self._telem_labels["lbl_el"].config(
                    text=f"{el:.2f}°",
                    fg=self.C["green"] if vis else self.C["red"])
                self._telem_labels["lbl_sentido"].config(
                    text=f"🌙 {dist_str}",
                    fg=self.C["yellow"])
                self._telem_labels["lbl_az_mot"].config(
                    text=f"{'VISIBLE' if vis else 'NO VISIBLE'}")
                self._telem_labels["lbl_el_mot"].config(text="")
                self._draw_polar()
                if ms:
                    self.log(ms, "data")
            self.root.after(0, _upd)

            self.root.after(0, lambda a=az, e=el, d=dist_str: self.log(
                f"ORION: AZ={a:.2f}° EL={e:.2f}° Dist={d}", "data"))

            time.sleep(interval)

        self.root.after(0, lambda: self.log("Seguimiento Horizons detenido", "warn"))

    # ── Mapa polar ───────────────────────────────────────────

    def _draw_polar(self):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20 or h < 20:
            return

        cx = w // 2
        cy = h // 2
        r  = min(w, h) // 2 - 28

        # Fondo circular
        c.create_oval(cx-r, cy-r, cx+r, cy+r,
                      fill="#050505", outline="#2a2a2a", width=2)

        # Anillos de elevación: 0°, 30°, 60°, 90°
        for el, lbl in [(0,"0°"), (30,"30°"), (60,"60°"), (90,"90°")]:
            pr = r * (90 - el) / 90
            c.create_oval(cx-pr, cy-pr, cx+pr, cy+pr,
                          outline="#1a1a1a", width=1)
            if el > 0 and pr > 20:
                c.create_text(cx + pr + 3, cy,
                              text=lbl, font=("Courier New", 7),
                              fill="#404040", anchor=tk.W)

        # Líneas cardinales N E S O
        for az_deg, label in [(0,"N"), (90,"E"), (180,"S"), (270,"O")]:
            rad = math.radians(az_deg)
            x1  = cx + (r * 0.08) * math.sin(rad)
            y1  = cy - (r * 0.08) * math.cos(rad)
            x2  = cx + r * math.sin(rad)
            y2  = cy - r * math.cos(rad)
            c.create_line(x1, y1, x2, y2, fill="#202020", dash=(3,4))
            xt = cx + (r + 14) * math.sin(rad)
            yt = cy - (r + 14) * math.cos(rad)
            c.create_text(xt, yt, text=label,
                          font=("Courier New", 9, "bold"),
                          fill="#909090", anchor=tk.CENTER)

        # Variables de zona horaria (usadas por Orion y Luna)
        use_utc = self.cfg.get("use_utc", True)
        tz_label = "UTC" if use_utc else "LOC"

        # ── Sistema de colocación inteligente de etiquetas ──
        # Registra todas las zonas ocupadas (rectángulos) para evitar solapamientos
        is_orion = is_horizons_object(self.selected_sat)
        self._occupied = []  # [(x1,y1,x2,y2), ...]

        def register_zone(x, y, w_half, h_half, margin=4):
            """Registra una zona rectangular como ocupada."""
            self._occupied.append((x - w_half - margin, y - h_half - margin,
                                   x + w_half + margin, y + h_half + margin))

        def is_free(x, y, w_half, h_half, margin=2):
            """Comprueba si una zona está libre de solapamientos."""
            ax1, ay1 = x - w_half - margin, y - h_half - margin
            ax2, ay2 = x + w_half + margin, y + h_half + margin
            for (bx1, by1, bx2, by2) in self._occupied:
                if ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1:
                    return False
            return True

        # Guardar referencia a nivel de instancia para usarla en _on_polar_motion
        self._is_free = is_free

        def best_label_pos(ref_x, ref_y, text_w, text_h, prefer_below=False):
            """Busca sitio libre MAS CERCANO — barrido angular por distancia."""
            hw = text_w // 2 + 4
            hh = text_h // 2 + 2
            angles_above = [0, 15, 345, 30, 330, 45, 315, 60, 300, 75, 285, 90, 270,
                            105, 255, 120, 240, 135, 225, 150, 210, 165, 195, 180]
            angles_below = list(reversed(angles_above))
            angles = angles_below if prefer_below else angles_above

            for dist in range(10, 60, 3):
                for ang in angles:
                    rad_a = math.radians(ang)
                    dx = dist * math.sin(rad_a)
                    dy = -dist * math.cos(rad_a)
                    tx, ty = ref_x + dx, ref_y + dy
                    if dx < -3: anchor = tk.E
                    elif dx > 3: anchor = tk.W
                    else: anchor = tk.CENTER
                    if is_free(tx, ty, 6, hh, margin=1):
                        if anchor == tk.W: center_x = tx + hw
                        elif anchor == tk.E: center_x = tx - hw
                        else: center_x = tx
                        register_zone(center_x, ty, hw, hh, margin=2)
                        return tx, ty, anchor
            # Fallback
            tx, ty = ref_x + 30, ref_y - 15
            register_zone(tx + hw, ty, hw, hh, margin=2)
            return tx, ty, tk.W

        def best_label_pos_2line(ref_x, ref_y, text_w, total_h=22, prefer_above=False):
            """Busca sitio libre MAS CERCANO al punto — barrido angular por distancia."""
            hw = text_w // 2 + 4
            hh = total_h // 2 + 2
            # 24 direcciones cada 15° para buscar el sitio mas cercano
            angles_above = [0, 15, 345, 30, 330, 45, 315, 60, 300, 75, 285, 90, 270,
                            105, 255, 120, 240, 135, 225, 150, 210, 165, 195, 180]
            angles_below = list(reversed(angles_above))
            angles = angles_above if prefer_above else angles_below

            # Barrido: probar CADA distancia en TODOS los angulos antes de alejarse
            for dist in range(10, 60, 3):  # 10, 13, 16, ... 58
                for ang in angles:
                    rad_a = math.radians(ang)
                    dx = dist * math.sin(rad_a)
                    dy = -dist * math.cos(rad_a)
                    tx, ty = ref_x + dx, ref_y + dy
                    if dx < -3: anchor = tk.E
                    elif dx > 3: anchor = tk.W
                    else: anchor = tk.CENTER
                    # Comprobar solo zona reducida (6x hh) cerca del ancla para poder acercarse mas
                    if is_free(tx, ty, 6, hh, margin=1):
                        # Registrar el area real completa del texto
                        if anchor == tk.W: center_x = tx + hw
                        elif anchor == tk.E: center_x = tx - hw
                        else: center_x = tx
                        register_zone(center_x, ty, hw, hh, margin=2)
                        return tx, ty, anchor
            # Fallback: arriba-derecha lejos
            tx, ty = ref_x + 40, ref_y - 20
            register_zone(tx + hw, ty, hw, hh, margin=2)
            return tx, ty, tk.W

        # Registrar zonas de la carta: anillos, cardinales, centro
        register_zone(cx, cy, 5, 5)  # centro
        for az_deg in [0, 90, 180, 270]:
            rad = math.radians(az_deg)
            xt = cx + (r + 14) * math.sin(rad)
            yt = cy - (r + 14) * math.cos(rad)
            register_zone(xt, yt, 8, 8)  # letras N E S O
        # Registrar etiquetas de elevación
        for el_deg in [30, 60, 90]:
            pr = r * (90 - el_deg) / 90
            register_zone(cx + pr + 10, cy, 12, 6)

        # Pre-registrar zonas de trayectorias Luna/Sol para que los rótulos
        # del satélite NO se coloquen encima de ellas
        for _pretrack in [self.moon_track, self.sun_track]:
            if _pretrack:
                _prev_px, _prev_py = None, None
                for _item in _pretrack:
                    if _item[1] > 0:
                        _px, _py = self._az_el_to_xy(_item[0], _item[1], cx, cy, r)
                        register_zone(_px, _py, 4, 4, margin=3)
                        if _prev_px is not None:
                            register_zone((_prev_px+_px)//2, (_prev_py+_py)//2, 4, 4, margin=3)
                        _prev_px, _prev_py = _px, _py
                    else:
                        _prev_px, _prev_py = None, None

        # Determinar si Orion está por debajo de la Luna
        orion_below_moon = False
        if is_orion and self.moon_track and self.future_track:
            orion_els = [item[1] for item in self.future_track if item[1] > 0]
            moon_els = [item[1] for item in self.moon_track if item[1] > 0]
            if orion_els and moon_els:
                avg_orion = sum(orion_els) / len(orion_els)
                avg_moon = sum(moon_els) / len(moon_els)
                orion_below_moon = avg_orion < avg_moon

        # ── Trayectoria satélite/Orion (misma función que Sol y Luna) ──
        self._track_screen_pts = []
        if len(self.future_track) > 1:
            if self.pass_index >= len(self.sat_passes):
                self.pass_index = 0
            _p = self.sat_passes[self.pass_index] if self.sat_passes else {}
            # Colores
            if is_orion:
                _sat_colors = {"line": "#e0b000", "fill": "#c0a000", "outline": "#806000",
                               "lbl": "#c0a000", "lbl2": "#806000"}
                _sat_visible = self._orion_visible
            else:
                _sat_colors = {"line": "#c0c0c0", "fill": "#707070", "outline": "#505050",
                               "lbl": "#787878", "lbl2": "#606060"}
                _sat_visible = True
            # rise/set UTC
            _sat_rise_utc = _p.get("rise_time")
            _sat_set_utc = _p.get("set_time")
            # Nombre corto
            _sat_name = self.selected_sat.split("(")[0].strip() if self.selected_sat else ""
            self._track_screen_pts, _ = self._draw_body_track(
                c, cx, cy, r,
                self.future_track, _sat_rise_utc, _sat_set_utc,
                None, _sat_visible, _sat_colors,
                "↑", "↓", "▲", _sat_name, 5, 4,
                register_zone, best_label_pos_2line,
                use_utc, tz_label,
                prefer_above=not orion_below_moon,
                rise_az=_p.get("rise_az"), set_az=_p.get("set_az"),
                check_above=False,
                line_width=1, line_dash=(6, 4))

        # ── Traza recorrida (lo que ya ha pasado) ──
        if len(self.pass_track) > 1:
            pts = []
            for az, el in self.pass_track:
                px, py = self._az_el_to_xy(az, el, cx, cy, r)
                pts += [px, py]
            track_col = "#c0a000" if is_horizons_object(self.selected_sat) else "#606060"
            c.create_line(*pts, fill=track_col, width=2)

        # ── Trayectoria de la Luna (función unificada) ──
        self._moon_screen_pts, _moon_now_above = self._draw_body_track(
            c, cx, cy, r,
            self.moon_track, self.moon_rise_utc, self.moon_set_utc,
            ephem.Moon, self._luna_visible,
            {"line": "#606060", "fill": "#404040", "outline": "#707070",
             "lbl": "#707070", "lbl2": "#606060"},
            "☽↑", "☽↓", "☽ ▲", "Luna", 6, 5,
            register_zone, best_label_pos_2line,
            use_utc, tz_label, prefer_above=not orion_below_moon)

        # ── Trayectoria del Sol (función unificada) ──
        # Azul junto a Orion, amarillo con los demás satélites
        if is_orion:
            _sun_colors = {"line": "#5090d0", "fill": "#4080c0", "outline": "#5090d0",
                           "lbl": "#5090d0", "lbl2": "#4070a0"}
            _sun_rect_on = "#4080c0"; _sun_rect_out_on = "#305080"
            _sun_rect_off = "#101520"; _sun_rect_out_off = "#203040"; _sun_rect_txt_off = "#304060"
        else:
            _sun_colors = {"line": "#c0a000", "fill": "#a08000", "outline": "#c0a000",
                           "lbl": "#c0a000", "lbl2": "#806000"}
            _sun_rect_on = "#c0a000"; _sun_rect_out_on = "#806000"
            _sun_rect_off = "#1a1500"; _sun_rect_out_off = "#403000"; _sun_rect_txt_off = "#504000"
        self._sun_screen_pts, _sun_now_above = self._draw_body_track(
            c, cx, cy, r,
            self.sun_track, self._sun_rise_utc, self._sun_set_utc,
            ephem.Sun, self._sun_visible,
            _sun_colors,
            "☀↑", "☀↓", "☀ ▲", "Sol", 4, 3,
            register_zone, best_label_pos_2line,
            use_utc, tz_label, prefer_above=False)

        # ── Punto actual del Sol (posición ahora) ──
        if self.sun_track and self._sun_visible and EPHEM_OK:
            try:
                _sun_pos = ephem.Sun()
                _obs_sp = ephem.Observer()
                _obs_sp.lat = str(self.cfg.get("obs_lat", OBS_LAT))
                _obs_sp.lon = str(self.cfg.get("obs_lon", OBS_LON))
                _obs_sp.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
                _obs_sp.date = self._get_now().replace(tzinfo=None)
                _sun_pos.compute(_obs_sp)
                _sun_az = float(_sun_pos.az) * DEG
                _sun_el = float(_sun_pos.alt) * DEG
                if _sun_el > 0:
                    _spx, _spy = self._az_el_to_xy(_sun_az, _sun_el, cx, cy, r)
                    # Comprobar si está cerca de otro punto — cambiar color
                    _near_other = False
                    for (zx1, zy1, zx2, zy2) in self._occupied:
                        zcx, zcy = (zx1+zx2)/2, (zy1+zy2)/2
                        if math.hypot(_spx - zcx, _spy - zcy) < 15:
                            _near_other = True
                            break
                    if _near_other:
                        _sc = "#ff6060"  # rojo cuando cerca de otro punto
                    else:
                        _sc = _sun_fill
                    c.create_oval(_spx-5, _spy-5, _spx+5, _spy+5,
                                  fill=_sc, outline="#ffffff", width=1)
                    c.create_text(_spx, _spy, text="☀",
                                  font=("Courier New", 6), fill="#000000")
            except Exception:
                pass

        # ── Punto actual de la Luna (posición ahora) ──
        if self.moon_track and self._luna_visible and EPHEM_OK:
            try:
                _moon_pos = ephem.Moon()
                _obs_mp = ephem.Observer()
                _obs_mp.lat = str(self.cfg.get("obs_lat", OBS_LAT))
                _obs_mp.lon = str(self.cfg.get("obs_lon", OBS_LON))
                _obs_mp.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
                _obs_mp.date = self._get_now().replace(tzinfo=None)
                _moon_pos.compute(_obs_mp)
                _moon_az = float(_moon_pos.az) * DEG
                _moon_el = float(_moon_pos.alt) * DEG
                if _moon_el > 0:
                    _mpx, _mpy = self._az_el_to_xy(_moon_az, _moon_el, cx, cy, r)
                    _near_other_m = False
                    for (zx1, zy1, zx2, zy2) in self._occupied:
                        zcx, zcy = (zx1+zx2)/2, (zy1+zy2)/2
                        if math.hypot(_mpx - zcx, _mpy - zcy) < 15:
                            _near_other_m = True
                            break
                    if _near_other_m:
                        _mc = "#ff6060"
                    else:
                        _mc = "#808080"
                    c.create_oval(_mpx-5, _mpy-5, _mpx+5, _mpy+5,
                                  fill=_mc, outline="#c0c0c0", width=1)
                    c.create_text(_mpx, _mpy, text="☽",
                                  font=("Courier New", 6), fill="#000000")
            except Exception:
                pass

        # ── Punto actual del satélite ──
        if self.selected_sat and self.el_now > 0:
            px, py = self._az_el_to_xy(self.az_now, self.el_now, cx, cy, r)

            if self.el_now > 0:
                if is_horizons_object(self.selected_sat):
                    # Orion: amarillo con halo
                    c.create_oval(px-12, py-12, px+12, py+12,
                                  fill="", outline="#806000", width=6)
                    c.create_oval(px-8, py-8, px+8, py+8,
                                  fill="#c0a000", outline="#e0c000", width=2)
                    c.create_line(px-14, py, px-9, py, fill="#c0a000", width=1)
                    c.create_line(px+9,  py, px+14, py, fill="#c0a000", width=1)
                    c.create_line(px, py-14, px, py-9, fill="#c0a000", width=1)
                    c.create_line(px, py+9,  px, py+14, fill="#c0a000", width=1)
                    register_zone(px, py, 14, 14)
                    sat_name = self.selected_sat[:16]
                    snw = len(sat_name) * 7
                    snx, sny, snanc = best_label_pos(px, py, snw, 10, prefer_below=orion_below_moon)
                    c.create_text(snx, sny,
                                  text=sat_name,
                                  font=("Courier New", 8, "bold"),
                                  fill="#e0c000", anchor=snanc)
                else:
                    # Satélites normales: gris/blanco
                    c.create_oval(px-12, py-12, px+12, py+12,
                                  fill="", outline="#404040", width=6)
                    c.create_oval(px-8, py-8, px+8, py+8,
                                  fill="#606060", outline="#a0a0a0", width=2)
                    c.create_line(px-14, py, px-9, py, fill="#606060", width=1)
                    c.create_line(px+9,  py, px+14, py, fill="#606060", width=1)
                    c.create_line(px, py-14, px, py-9, fill="#606060", width=1)
                    c.create_line(px, py+9,  px, py+14, fill="#606060", width=1)
                    register_zone(px, py, 14, 14)
                    sat_name = self.selected_sat[:16]
                    snw = len(sat_name) * 7
                    snx, sny, snanc = best_label_pos(px, py, snw, 10, prefer_below=orion_below_moon)
                    c.create_text(snx, sny,
                                  text=sat_name,
                                  font=("Courier New", 8, "bold"),
                                  fill="#606060", anchor=snanc)

        # ── Sentido: siempre visible arriba-izquierda de la carta ──
        if self.sentido:
            arrow = "↻" if self.sentido == "Horario" else "↺"
            sent_text = f"{arrow} {self.sentido}"
            c.create_text(8, 12,
                          text=sent_text,
                          font=("Courier New", 10, "bold"),
                          fill="#a0a0a0", anchor=tk.W)

        # ── Leyenda abajo-derecha (siempre visible) ──
        self._legend_rects = []
        lx = w - 85
        # Calculate how many legend items we need
        _legend_items = []
        if is_orion:
            _legend_items.append("orion")
        # Solo mostrar rectángulo si está AHORA sobre el horizonte
        moon_now_above = False
        sun_now_above = False
        if EPHEM_OK:
            try:
                _obs_now = ephem.Observer()
                _obs_now.lat = str(self.cfg.get("obs_lat", OBS_LAT))
                _obs_now.lon = str(self.cfg.get("obs_lon", OBS_LON))
                _obs_now.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
                _obs_now.date = self._get_now().replace(tzinfo=None)
                _moon_now = ephem.Moon()
                _moon_now.compute(_obs_now)
                moon_now_above = float(_moon_now.alt) * DEG > 0
                _sun_now = ephem.Sun()
                _sun_now.compute(_obs_now)
                sun_now_above = float(_sun_now.alt) * DEG > 0
            except Exception:
                pass
        has_visible_moon = moon_now_above and bool(self.moon_track)
        has_visible_sun = sun_now_above and bool(self.sun_track)
        if has_visible_moon:
            _legend_items.append("luna")
        if has_visible_sun:
            _legend_items.append("sol")
        if _legend_items:
            ly = h - 16 - len(_legend_items) * 16
            _ly_cur = ly
            for _leg in _legend_items:
                if _leg == "orion":
                    if self._orion_visible:
                        c.create_rectangle(lx, _ly_cur, lx + 60, _ly_cur + 13,
                                           fill="#c0a000", outline="#806000", width=1)
                        c.create_text(lx + 30, _ly_cur + 7, text="ORION",
                                      font=("Courier New", 7, "bold"), fill="#000000")
                    else:
                        c.create_rectangle(lx, _ly_cur, lx + 60, _ly_cur + 13,
                                           fill="#1a1500", outline="#403000", width=1)
                        c.create_text(lx + 30, _ly_cur + 7, text="ORION",
                                      font=("Courier New", 7), fill="#504000")
                    self._legend_rects.append((lx, _ly_cur, lx + 60, _ly_cur + 13, "orion"))
                elif _leg == "luna":
                    if self._luna_visible:
                        c.create_rectangle(lx, _ly_cur, lx + 60, _ly_cur + 13,
                                           fill="#707070", outline="#505050", width=1)
                        c.create_text(lx + 30, _ly_cur + 7, text="LUNA",
                                      font=("Courier New", 7, "bold"), fill="#000000")
                    else:
                        c.create_rectangle(lx, _ly_cur, lx + 60, _ly_cur + 13,
                                           fill="#151515", outline="#303030", width=1)
                        c.create_text(lx + 30, _ly_cur + 7, text="LUNA",
                                      font=("Courier New", 7), fill="#404040")
                    self._legend_rects.append((lx, _ly_cur, lx + 60, _ly_cur + 13, "luna"))
                elif _leg == "sol":
                    if self._sun_visible:
                        c.create_rectangle(lx, _ly_cur, lx + 60, _ly_cur + 13,
                                           fill=_sun_rect_on, outline=_sun_rect_out_on, width=1)
                        c.create_text(lx + 30, _ly_cur + 7, text="SOL",
                                      font=("Courier New", 7, "bold"), fill="#000000")
                    else:
                        c.create_rectangle(lx, _ly_cur, lx + 60, _ly_cur + 13,
                                           fill=_sun_rect_off, outline=_sun_rect_out_off, width=1)
                        c.create_text(lx + 30, _ly_cur + 7, text="SOL",
                                      font=("Courier New", 7), fill=_sun_rect_txt_off)
                    self._legend_rects.append((lx, _ly_cur, lx + 60, _ly_cur + 13, "sol"))
                _ly_cur += 16

    def _draw_body_track(self, c, cx, cy, r, track, rise_utc, set_utc,
                          body_cls, visible, colors, sym_up, sym_down,
                          sym_max, name, pt_r, pt_r_max,
                          register_zone, best_label_pos_2line,
                          use_utc, tz_label, prefer_above=False,
                          rise_az=None, set_az=None, check_above=True,
                          line_width=1, line_dash=(3, 3)):
        """Función ÚNICA para dibujar trayectoria + 3 puntos (rise/max/set).
        Sirve para Sol, Luna, satélites y Orion — misma lógica, distintos colores.
        Devuelve (screen_pts, drawn).
        body_cls: ephem.Sun/ephem.Moon para Sol/Luna, None para satélites/Orion.
        rise_az/set_az: azimut directo (satélites/Orion). Si None, calcula con body_cls.
        check_above: True para Sol/Luna (solo dibuja si está sobre horizonte), False para satélites."""
        screen_pts = []
        if not track or not visible:
            return screen_pts, False
        # ── Gate: comprobar si el cuerpo está sobre el horizonte ──
        if check_above:
            if not EPHEM_OK or not body_cls:
                return screen_pts, False
            try:
                _obs = ephem.Observer()
                _obs.lat = str(self.cfg.get("obs_lat", OBS_LAT))
                _obs.lon = str(self.cfg.get("obs_lon", OBS_LON))
                _obs.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
                _obs.date = self._get_now().replace(tzinfo=None)
                _body = body_cls()
                _body.compute(_obs)
                if float(_body.alt) <= 0:
                    return screen_pts, False
            except Exception:
                return screen_pts, False
        # ── Trayectoria segmentada (corta en huecos el<0) ──
        segments = []
        cur_seg = []
        screen = []
        prev_up = False
        for item in track:
            az, el = item[0], item[1]
            ts = item[2] if len(item) > 2 else ""
            if el >= 0:
                px, py = self._az_el_to_xy(az, el, cx, cy, r)
                cur_seg += [px, py]
                screen.append((px, py))
                screen_pts.append((px, py, az, el, ts))
                prev_up = True
            else:
                if prev_up and len(cur_seg) >= 4:
                    segments.append(cur_seg)
                cur_seg = []
                prev_up = False
        if prev_up and len(cur_seg) >= 4:
            segments.append(cur_seg)
        # Registrar zonas
        for i in range(len(screen)):
            px_i, py_i = screen[i]
            register_zone(px_i, py_i, 4, 4, margin=3)
            if i + 1 < len(screen):
                px_n, py_n = screen[i+1]
                register_zone((px_i+px_n)//2, (py_i+py_n)//2, 4, 4, margin=3)
        # Dibujar segmentos
        for seg in segments:
            c.create_line(*seg, fill=colors["line"], width=line_width, dash=line_dash)
        # ── 3 puntos: RISE / MAX / SET ──
        lbl1 = colors["lbl"]
        lbl2 = colors["lbl2"]
        fill = colors["fill"]
        out = colors["outline"]
        # Calcular az de rise/set
        _az_rise = rise_az  # directo (satélites/Orion)
        _az_set = set_az
        if body_cls and EPHEM_OK and rise_utc and not rise_az:
            try:
                _obs = ephem.Observer()
                _obs.lat = str(self.cfg.get("obs_lat", OBS_LAT))
                _obs.lon = str(self.cfg.get("obs_lon", OBS_LON))
                _obs.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
                _b = body_cls()
                _obs.date = rise_utc.strftime("%Y/%m/%d %H:%M:%S")
                _b.compute(_obs)
                _az_rise = float(_b.az) * DEG
                if set_utc:
                    _obs.date = set_utc.strftime("%Y/%m/%d %H:%M:%S")
                    _b.compute(_obs)
                    _az_set = float(_b.az) * DEG
            except Exception:
                pass
        # Calcular max el/az
        _az_max, _el_max = None, None
        if body_cls and EPHEM_OK and rise_utc and set_utc:
            try:
                _obs = ephem.Observer()
                _obs.lat = str(self.cfg.get("obs_lat", OBS_LAT))
                _obs.lon = str(self.cfg.get("obs_lon", OBS_LON))
                _obs.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
                _b = body_cls()
                mid_t = rise_utc + (set_utc - rise_utc) / 2
                _obs.date = mid_t.strftime("%Y/%m/%d %H:%M:%S")
                _b.compute(_obs)
                _az_max = float(_b.az) * DEG
                _el_max = float(_b.alt) * DEG
            except Exception:
                pass
        if _az_max is None and screen_pts:
            # Fallback: max del track (satélites/Orion)
            mx = max(screen_pts, key=lambda p: p[3])
            _az_max, _el_max = mx[2], mx[3]
        # Formatear horas
        _rise_hhmm = ""
        if rise_utc:
            _rise_hhmm = rise_utc.strftime("%d/%m %H:%M") if use_utc else rise_utc.astimezone().strftime("%d/%m %H:%M")
        _set_hhmm = ""
        if set_utc:
            _set_hhmm = set_utc.strftime("%d/%m %H:%M") if use_utc else set_utc.astimezone().strftime("%d/%m %H:%M")
        # ── RISE ──
        if _az_rise is not None:
            px0, py0 = self._az_el_to_xy(_az_rise, 0.0, cx, cy, r)
            c.create_oval(px0-pt_r, py0-pt_r, px0+pt_r, py0+pt_r,
                          fill=fill, outline=out, width=1)
            register_zone(px0, py0, pt_r+1, pt_r+1)
            t1 = f"{sym_up} {_az_rise:.0f}°"
            t2 = f"{_rise_hhmm}{tz_label}" if _rise_hhmm else ""
            tw = max(len(t1), len(t2) if t2 else 0) * 5
            lx, ly, anc = best_label_pos_2line(px0, py0, tw, 20, prefer_above=prefer_above)
            c.create_text(lx, ly-5, text=t1, font=("Courier New", 6), fill=lbl1, anchor=anc)
            if t2:
                c.create_text(lx, ly+5, text=t2, font=("Courier New", 6), fill=lbl2, anchor=anc)
        # ── MAX ──
        if _az_max is not None and _el_max is not None:
            px_mx, py_mx = self._az_el_to_xy(_az_max, _el_max, cx, cy, r)
            c.create_oval(px_mx-pt_r_max, py_mx-pt_r_max, px_mx+pt_r_max, py_mx+pt_r_max,
                          fill=fill, outline=out, width=1)
            register_zone(px_mx, py_mx, pt_r_max+1, pt_r_max+1)
            # Hora del max: punto medio entre rise y set
            _max_hhmm = ""
            if rise_utc and set_utc:
                _max_t = rise_utc + (set_utc - rise_utc) / 2
                _max_hhmm = _max_t.strftime("%d/%m %H:%M") if use_utc else _max_t.astimezone().strftime("%d/%m %H:%M")
            t1 = f"{sym_max}{_el_max:.0f}° {name}"
            t2 = f"{_max_hhmm}{tz_label}" if _max_hhmm else ""
            tw = max(len(t1), len(t2) if t2 else 0) * 5
            lx, ly, anc = best_label_pos_2line(px_mx, py_mx, tw, 22, prefer_above=prefer_above)
            c.create_text(lx, ly-6, text=t1,
                          font=("Courier New", 7, "bold"), fill=lbl1, anchor=anc)
            if t2:
                c.create_text(lx, ly+6, text=t2,
                              font=("Courier New", 6), fill=lbl2, anchor=anc)
        # ── SET ──
        if _az_set is not None:
            pxf, pyf = self._az_el_to_xy(_az_set, 0.0, cx, cy, r)
            c.create_oval(pxf-pt_r, pyf-pt_r, pxf+pt_r, pyf+pt_r,
                          fill=fill, outline=out, width=1)
            register_zone(pxf, pyf, pt_r+2, pt_r+2)
            t1 = f"{sym_down} {_az_set:.0f}°"
            t2 = f"{_set_hhmm}{tz_label}" if _set_hhmm else ""
            tw = max(len(t1), len(t2) if t2 else 0) * 5
            lx, ly, anc = best_label_pos_2line(pxf, pyf, tw, 20, prefer_above=prefer_above)
            c.create_text(lx, ly-5, text=t1, font=("Courier New", 6), fill=lbl1, anchor=anc)
            if t2:
                c.create_text(lx, ly+5, text=t2, font=("Courier New", 6), fill=lbl2, anchor=anc)
        return screen_pts, True

    def _az_el_to_xy(self, az: float, el: float,
                      cx: int, cy: int, r: int) -> tuple:
        el   = max(el, 0)
        dist = r * (90 - el) / 90
        rad  = math.radians(az)
        return cx + dist * math.sin(rad), cy - dist * math.cos(rad)

    def _on_polar_click(self, event):
        """Click en la carta polar — toggle Orion/Luna con los rectángulos."""
        mx, my = event.x, event.y
        for (rx1, ry1, rx2, ry2, layer) in self._legend_rects:
            if rx1 <= mx <= rx2 and ry1 <= my <= ry2:
                if layer == "orion":
                    self._orion_visible = not self._orion_visible
                elif layer == "luna":
                    self._luna_visible = not self._luna_visible
                elif layer == "sol":
                    self._sun_visible = not self._sun_visible
                self._draw_polar()
                return

    def _on_polar_motion(self, event):
        """Tooltip al pasar el ratón sobre la trayectoria en el mapa polar.
        Mismo patrón que _on_world_motion (simple, sin tags, sin flicker)."""
        c = self.canvas
        mx, my = event.x, event.y

        # Borrar tooltip anterior por ID
        if self._polar_tooltip:
            c.delete(self._polar_tooltip)
            self._polar_tooltip = None
        if hasattr(self, '_polar_tooltip2') and self._polar_tooltip2:
            c.delete(self._polar_tooltip2)
            self._polar_tooltip2 = None

        # Buscar en trayectoria principal, Luna y Sol
        all_pts = list(self._track_screen_pts)
        if hasattr(self, '_moon_screen_pts'):
            all_pts += self._moon_screen_pts
        if hasattr(self, '_sun_screen_pts'):
            all_pts += self._sun_screen_pts

        if not all_pts:
            self._hover_active = False
            return

        mx, my = event.x, event.y
        best_d = 15  # radio máximo en pixels
        best_pt = None
        for (px, py, az, el, ts) in all_pts:
            d = math.hypot(mx - px, my - py)
            if d < best_d:
                best_d = d
                best_pt = (px, py, az, el, ts)

        if best_pt:
            import time as _t
            self._hover_active = True
            self._last_hover_time = _t.time()
            px, py, az, el, ts = best_pt

            # Formatear hora
            use_utc = self.cfg.get("use_utc", True)
            tz_label = "UTC" if use_utc else "LOC"
            _months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                       "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
            hhmm = ""
            if ts and " " in ts:
                if use_utc:
                    hhmm = ts.split()[-1]
                else:
                    try:
                        parts = ts.replace("-", " ").split()
                        yr, mo = int(parts[0]), _months.get(parts[1], 1)
                        dy = int(parts[2])
                        hh, mm = parts[3].split(":")
                        dt_utc = datetime(yr, mo, dy, int(hh), int(mm), tzinfo=timezone.utc)
                        hhmm = dt_utc.astimezone().strftime("%H:%M")
                    except Exception:
                        hhmm = ts.split()[-1]

            tip_line1 = f"Az={az:.1f}° El={el:.1f}°"
            tip_line2 = f"{hhmm}{tz_label}" if hhmm else ""

            # Posición: usar curvatura (producto cruz) para poner texto
            # FUERA de la curva (lado convexo)
            idx = None
            for i, (spx, spy, _, _, _) in enumerate(self._track_screen_pts):
                if spx == px and spy == py:
                    idx = i
                    break
            put_above = True  # default
            if idx is not None and len(self._track_screen_pts) >= 3:
                i_prev = max(0, idx - 1)
                i_next = min(len(self._track_screen_pts) - 1, idx + 1)
                if i_prev != idx and i_next != idx:
                    ppx, ppy = self._track_screen_pts[i_prev][0], self._track_screen_pts[i_prev][1]
                    npx, npy = self._track_screen_pts[i_next][0], self._track_screen_pts[i_next][1]
                    # Vectores: prev→current y current→next
                    v1x, v1y = px - ppx, py - ppy
                    v2x, v2y = npx - px, npy - py
                    # Producto cruz: signo indica lado de curvatura
                    cross = v1x * v2y - v1y * v2x
                    # cross > 0 → curva gira a la derecha (en pantalla) → fuera es arriba/izq
                    # cross < 0 → curva gira a la izquierda → fuera es abajo/der
                    # Perpendicular al segmento tangente apuntando FUERA de la curva
                    tangx = npx - ppx
                    tangy = npy - ppy
                    tlen = math.hypot(tangx, tangy) or 1
                    # Normal: rotar tangente 90° hacia el lado convexo
                    if cross > 0:
                        # Curva hacia derecha → normal hacia izquierda (arriba en muchos casos)
                        ny = -tangx / tlen
                    else:
                        # Curva hacia izquierda → normal hacia derecha (abajo en muchos casos)
                        ny = tangx / tlen
                    put_above = ny < 0  # si normal apunta hacia arriba → texto arriba

            # Buscar sitio libre para el tooltip sin chocar con nada
            tip_hw = len(tip_line1) * 4 + 4
            tip_hh = 12 if tip_line2 else 6
            tip_placed = False
            prefer_dirs = [0, 15, 345, 30, 330, 45, 315, 90, 270] if put_above else [180, 195, 165, 210, 150, 225, 135, 90, 270]
            for dist in [14, 18, 24, 32]:
                for ang in prefer_dirs:
                    rad_a = math.radians(ang)
                    tx = px + dist * math.sin(rad_a)
                    ty = py - dist * math.cos(rad_a)
                    if tx < px - 3: anc = tk.E
                    elif tx > px + 3: anc = tk.W
                    else: anc = tk.CENTER
                    if hasattr(self, '_is_free') and self._is_free(tx, ty, 6, tip_hh, margin=1):
                        if tip_line2:
                            id1 = c.create_text(tx, ty - 5, text=tip_line1,
                                font=("Courier New", 7), fill="#e0e0e0", anchor=anc)
                            id2 = c.create_text(tx, ty + 5, text=tip_line2,
                                font=("Courier New", 6), fill="#b0b0b0", anchor=anc)
                            self._polar_tooltip = id1  # guardar uno para borrar
                            self._polar_tooltip2 = id2
                        else:
                            self._polar_tooltip = c.create_text(
                                tx, ty, text=tip_line1,
                                font=("Courier New", 7), fill="#e0e0e0", anchor=anc)
                        tip_placed = True
                        break
                if tip_placed:
                    break
            if not tip_placed:
                if tip_line2:
                    self._polar_tooltip = c.create_text(
                        px + 14, py - 18, text=tip_line1,
                        font=("Courier New", 7), fill="#e0e0e0", anchor=tk.W)
                    self._polar_tooltip2 = c.create_text(
                        px + 14, py - 8, text=tip_line2,
                        font=("Courier New", 6), fill="#b0b0b0", anchor=tk.W)
                else:
                    self._polar_tooltip = c.create_text(
                        px + 14, py - 14, text=tip_line1,
                        font=("Courier New", 7), fill="#e0e0e0", anchor=tk.W)
        else:
            self._hover_active = False

    # ── Seguimiento en tiempo real ───────────────────────────

    def _toggle_tracking(self):
        if self.tracking:
            self.tracking = False
            self.btn_track.config(text="▶  INICIAR SEGUIMIENTO",
                                   fg=self.C["accent"], state=tk.NORMAL)
            self.log("■ Seguimiento detenido", "warn")
        else:
            if not self.selected_sat:
                messagebox.showwarning("Aviso", "Selecciona un satélite primero")
                return
            # Orion usa Horizons, no necesita ephem
            use_horizons = is_horizons_object(self.selected_sat)
            if not use_horizons and not EPHEM_OK:
                messagebox.showerror("Error",
                    "ephem no está instalado.\nEjecuta:  pip install ephem")
                return
            if use_horizons and not REQUESTS_OK:
                messagebox.showerror("Error",
                    "requests no está instalado.\nEjecuta:  pip install requests")
                return
            if use_horizons and not self.sat_passes:
                messagebox.showwarning("Aviso",
                    "Espera a que se descarguen los datos de Horizons")
                return
            self.tracking = True
            self.pass_track = []
            self.v0_az      = None
            self.btn_track.config(text="■  DETENER SEGUIMIENTO",
                                   fg=self.C["red"])
            if use_horizons:
                self.log(f"▶ Iniciando seguimiento CISLUNAR: {self.selected_sat}", "ok")
                self.log("  Usando NASA Horizons (no TLEs)", "info")
                self.track_thread = threading.Thread(
                    target=self._track_loop_horizons, daemon=True)
            else:
                self.log(f"▶ Iniciando seguimiento: {self.selected_sat}", "ok")
                self.track_thread = threading.Thread(
                    target=self._track_loop, daemon=True)
            self.track_thread.start()

    def _track_loop(self):
        """Bucle principal de seguimiento (hilo separado)."""
        sat_name = self.selected_sat
        l1, l2   = self.satellites[sat_name]
        interval = self.interval_var.get()
        mode     = self.mode_var.get()

        satellite = ephem.readtle(sat_name, l1, l2)
        obs = self._make_observer()

        # Detectar sentido orbital
        if mode == "auto":
            self.root.after(0, lambda: self.log("Detectando sentido orbital...", "info"))
            az_samples = []
            for _ in range(3):
                obs.date = datetime.now(timezone.utc).replace(tzinfo=None)
                satellite.compute(obs)
                az_samples.append(satellite.az * DEG)
                time.sleep(2.5)
            if len(az_samples) >= 2:
                diff = az_samples[-1] - az_samples[0]
                if abs(diff) > 180:
                    diff -= 360 if diff > 0 else -360
                self.sentido = "Horario" if diff >= 0 else "Antihorario"
        elif mode == "cw":
            self.sentido = "Horario"
        else:
            self.sentido = "Antihorario"

        sentido_log = self.sentido
        self.root.after(0, lambda s=sentido_log:
                        self.log(f"Sentido: {s}", "ok"))

        ya_visible = False
        v0         = 0.0

        while self.tracking and self.selected_sat == sat_name:
            obs.date = datetime.now(timezone.utc).replace(tzinfo=None)
            satellite.compute(obs)
            az = satellite.az  * DEG
            el = satellite.alt * DEG

            self.az_now = az
            self.el_now = el

            if not ya_visible:
                v0 = round(az)

            if el > 0:
                ya_visible = True
                vf = round(az)
                al = round(el)

                # Calcular ángulo del servo AZ
                if self.sentido == "Horario":
                    if vf - v0 >= 0:
                        az_motor = 180 - (vf - v0)
                    else:
                        az_motor = 180 - ((360 + vf) - v0)
                else:  # Antihorario
                    if v0 - vf >= 0:
                        az_motor = v0 - vf
                    else:
                        az_motor = v0 + (360 - vf)

                az_motor = max(0, min(180, az_motor))

                self._send_serial(az_motor, al)
                self.pass_track.append((az, el))

                def _upd(az=az, el=el, az_m=az_motor, el_m=al):
                    self._telem_labels["lbl_az"].config(
                        text=f"{az:.1f}°", fg=self.C["accent"])
                    self._telem_labels["lbl_el"].config(
                        text=f"{el:.1f}°", fg=self.C["green"])
                    arrow = "↻" if self.sentido == "Horario" else "↺"
                    self._telem_labels["lbl_sentido"].config(
                        text=f"{arrow} {self.sentido}",
                        fg=self.C["green"] if self.sentido == "Horario"
                        else self.C["yellow"])
                    self._telem_labels["lbl_az_mot"].config(text=f"{az_m}°")
                    self._telem_labels["lbl_el_mot"].config(text=f"{el_m}°")
                    self._draw_polar()
                self.root.after(0, _upd)

            else:
                if ya_visible:
                    ya_visible = False
                    self.root.after(0, lambda: self.log(
                        "Satélite bajo el horizonte", "warn"))
                v0 = round(az)

                def _upd_low(az=az, el=el):
                    self._telem_labels["lbl_az"].config(
                        text=f"{az:.1f}°", fg=self.C["muted"])
                    self._telem_labels["lbl_el"].config(
                        text=f"{el:.1f}°", fg=self.C["yellow"])
                    self._draw_polar()
                self.root.after(0, _upd_low)

            time.sleep(interval)

        self.root.after(0, lambda: self.log(
            "Seguimiento finalizado", "warn"))

    def _make_observer(self) -> ephem.Observer:
        obs = ephem.Observer()
        obs.lat       = self.cfg.get("obs_lat",  OBS_LAT)
        obs.lon       = self.cfg.get("obs_lon",  OBS_LON)
        obs.elevation = int(self.cfg.get("obs_elev", OBS_ELEV))
        obs.date      = self._get_now().replace(tzinfo=None)
        return obs

    # ── Calcular trayectoria de un pase ──────────────────────

    def _calc_single_pass(self):
        """Botón manual — recalcula pases del satélite seleccionado."""
        if not self.selected_sat:
            messagebox.showwarning("Aviso", "Selecciona un satélite primero")
            return
        self.sat_passes = []
        self.pass_index = 0
        if is_horizons_object(self.selected_sat):
            self.log("Consultando NASA Horizons para trayectoria...", "info")
            threading.Thread(target=self._load_horizons_pass, daemon=True).start()
        else:
            if not EPHEM_OK:
                return
            self.log("Calculando trayectoria...", "info")
            threading.Thread(target=self._load_sat_passes, daemon=True).start()

    def _load_horizons_pass(self):
        """Calcula el 'pase' de un objeto cislunar via NASA Horizons (hilo separado)."""
        sat_name = self.selected_sat
        self.root.after(0, lambda: self.log("Descargando trayectoria de Horizons (24h)...", "info"))

        def _reenable_btn():
            self.btn_track.config(text="▶  INICIAR SEGUIMIENTO", state=tk.NORMAL)

        if not REQUESTS_OK:
            self.root.after(0, lambda: self.log("Error: instala requests", "err"))
            self.root.after(0, _reenable_btn)
            return

        target = HORIZONS_OBJECTS.get(sat_name, "-180")
        now = self._get_now()
        # Empezar 12h antes para capturar el rise real si ya está visible
        start = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M")
        stop = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")

        lat_f = float(self.cfg.get("obs_lat", OBS_LAT))
        lon_f = float(self.cfg.get("obs_lon", OBS_LON))
        alt_km = float(self.cfg.get("obs_elev", OBS_ELEV)) / 1000.0

        body = (
            f"format=json"
            f"&COMMAND='{target}'"
            f"&OBJ_DATA=NO"
            f"&MAKE_EPHEM=YES"
            f"&EPHEM_TYPE=OBSERVER"
            f"&CENTER='coord@399'"
            f"&COORD_TYPE=GEODETIC"
            f"&SITE_COORD='{lon_f},{lat_f},{alt_km}'"
            f"&START_TIME='{start}'"
            f"&STOP_TIME='{stop}'"
            f"&STEP_SIZE='1 m'"
            f"&QUANTITIES='4'"
            f"&ANG_FORMAT=DEG"
            f"&TIME_ZONE='+00:00'"
        )

        try:
            req = urllib.request.Request(
                HORIZONS_URL,
                data=body.encode(),
                headers={'User-Agent': 'OrionTracker/4.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
            result = data.get("result", "")
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Error Horizons: {e}", "err"))
            self.root.after(0, _reenable_btn)
            return

        # Parsear todos los puntos
        # Formato: " 2026-Apr-05 03:39  t  181.48  22.78"
        lines = result.split("\n")
        in_data = False
        points = []  # [(az, el, time_str)]
        for line in lines:
            if "$$SOE" in line:
                in_data = True
                continue
            if "$$EOE" in line:
                break
            if in_data and line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        time_str = f"{parts[0]} {parts[1]}"  # "2026-Apr-05 03:39"
                        az = float(parts[3])
                        el = float(parts[4])
                        points.append((az, el, time_str))
                    except (ValueError, IndexError):
                        continue

        if not points:
            self.root.after(0, lambda: self.log("No hay datos de Horizons", "err"))
            self.root.after(0, _reenable_btn)
            return

        # Encontrar el pase que contiene NOW (o el próximo si está bajo horizonte)
        # Datos van desde now-12h hasta now+24h con paso de 1 min
        _data_start = now - timedelta(hours=12)
        _now_idx = 12 * 60  # índice correspondiente a "now" en los datos

        # Separar pases (tramos continuos con el>0)
        _passes = []  # [(start_idx, end_idx)]
        _in_pass = False
        _pass_start = 0
        for i, (az, el, ts) in enumerate(points):
            if el > 0 and not _in_pass:
                _pass_start = i
                _in_pass = True
            elif el <= 0 and _in_pass:
                _passes.append((_pass_start, i - 1))
                _in_pass = False
        if _in_pass:
            _passes.append((_pass_start, len(points) - 1))

        # Elegir el pase que contiene now_idx, o el más cercano futuro
        aos_idx = None
        los_idx = None
        for _ps, _pe in _passes:
            if _ps <= _now_idx <= _pe:
                aos_idx, los_idx = _ps, _pe
                break
        if aos_idx is None:
            # No está en un pase ahora — coger el próximo
            for _ps, _pe in _passes:
                if _ps > _now_idx:
                    aos_idx, los_idx = _ps, _pe
                    break
        if aos_idx is None and _passes:
            aos_idx, los_idx = _passes[0]

        max_el = -90
        max_el_idx = aos_idx or 0
        if aos_idx is not None:
            for i in range(aos_idx, los_idx + 1):
                if points[i][1] > max_el:
                    max_el = points[i][1]
                    max_el_idx = i

        # Track: pase seleccionado, empezando y terminando en el horizonte (el=0)
        track = []
        if aos_idx is not None:
            # Interpolar rise real (donde el cruza 0) entre último el<0 y primero el>0
            if aos_idx > 0:
                _a = points[aos_idx - 1]  # último el<0
                _b = points[aos_idx]      # primero el>0
                _frac = abs(_a[1]) / (abs(_a[1]) + _b[1]) if (abs(_a[1]) + _b[1]) > 0 else 0.5
                _rise_az_interp = _a[0] + _frac * (_b[0] - _a[0])
            else:
                _rise_az_interp = points[aos_idx][0]
            track.append((_rise_az_interp, 0.0, points[aos_idx][2]))
            for i in range(aos_idx, los_idx + 1):
                track.append(points[i])
            # Interpolar set real entre último el>0 y primero el<0
            if los_idx + 1 < len(points):
                _c = points[los_idx]      # último el>0
                _d = points[los_idx + 1]  # primero el<0
                _frac2 = _c[1] / (_c[1] + abs(_d[1])) if (_c[1] + abs(_d[1])) > 0 else 0.5
                _set_az_interp = _c[0] + _frac2 * (_d[0] - _c[0])
            else:
                _set_az_interp = points[los_idx][0]
            track.append((_set_az_interp, 0.0, points[los_idx][2]))

        if aos_idx is None:
            self.root.after(0, lambda: self.log(
                f"Orion bajo el horizonte desde Valencia las próximas 24h", "warn"))
            self.root.after(0, _reenable_btn)
            return

        # Crear pase — usar tiempos REALES y azimuts INTERPOLADOS
        az_rise = _rise_az_interp
        az_set = _set_az_interp
        time_rise = points[aos_idx][2]  # "2026-Apr-05 23:39"
        time_set = points[los_idx][2]
        time_max = points[max_el_idx][2]

        # Parser de timestamp Horizons → datetime UTC
        _months_parse = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                         "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
        def _parse_horizons_ts(ts):
            try:
                p = ts.replace("-", " ").split()
                return datetime(int(p[0]), _months_parse[p[1]], int(p[2]),
                                int(p[3].split(":")[0]), int(p[3].split(":")[1]),
                                tzinfo=timezone.utc)
            except Exception:
                return None

        rise_dt = _parse_horizons_ts(time_rise)
        set_dt = _parse_horizons_ts(time_set)
        max_dt = _parse_horizons_ts(time_max)
        duration_s = int((set_dt - rise_dt).total_seconds()) if rise_dt and set_dt else 0

        sentido = "Horario" if az_set > az_rise else "Antihorario"

        def hhmm(ts):
            return ts.split()[-1] if ts else "??:??"

        pass_info = {
            "sat_name": sat_name,
            "rise_time": rise_dt,
            "rise_az": az_rise,
            "max_el": max_el,
            "max_time": max_dt,
            "set_time": set_dt,
            "set_az": az_set,
            "duration_s": duration_s,
            "sentido": sentido,
            "track": track,
            "time_rise_str": time_rise,
            "time_set_str": time_set,
            "time_max_str": time_max,
        }

        # Check if user switched satellite while we were downloading
        if self.selected_sat != sat_name:
            self.root.after(0, _reenable_btn)
            return

        self.sat_passes = [pass_info]
        self.pass_index = 0
        # Convertir time_rise de string Horizons a datetime para mostrar ambas zonas
        _months_log = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                       "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
        def _to_local(ts):
            try:
                p = ts.replace("-"," ").split()
                dt = datetime(int(p[0]), _months_log[p[1]], int(p[2]),
                              int(p[3].split(":")[0]), int(p[3].split(":")[1]),
                              tzinfo=timezone.utc)
                return dt.astimezone().strftime("%H:%M %Z")
            except:
                return "?"

        self.root.after(0, lambda: self.log(
            f"🌙 SALE {hhmm(time_rise)} UTC ({_to_local(time_rise)}) Az={az_rise:.0f}°  "
            f"MAX {hhmm(time_max)} UTC ({_to_local(time_max)}) El={max_el:.1f}°  "
            f"PONE {hhmm(time_set)} UTC ({_to_local(time_set)}) Az={az_set:.0f}°  "
            f"Dur={duration_s//3600}h{(duration_s%3600)//60:02d}m", "ok"))

        # Luna se calcula en _calculate_sun_moon_tracks() — sin duplicados

        # Calcular posición de Orion en el mapamundi
        subpoint = self._get_orion_subpoint()
        if subpoint:
            self._orion_subpoint = subpoint
            self.root.after(0, self._draw_world)

        # Check again after download
        if self.selected_sat != sat_name:
            self.root.after(0, _reenable_btn)
            return

        self.root.after(0, self._show_current_pass)
        self.root.after(0, _reenable_btn)

    def _load_sat_passes(self):
        """Calcula todos los pases del satélite seleccionado (hilo separado)."""
        sat_name = self.selected_sat
        passes = compute_next_passes(
            sat_name,
            *self.satellites[sat_name],
            self.cfg.get("obs_lat",  OBS_LAT),
            self.cfg.get("obs_lon",  OBS_LON),
            int(self.cfg.get("obs_elev", OBS_ELEV)),
            hours=48.0, min_el=0.0,
            start_time=self._get_now())

        if not passes:
            self.root.after(0, lambda: self.log("Sin pases en 48h", "warn"))
            return

        # Para cada pase calcular su trayectoria punto a punto
        for p in passes:
            track = []
            try:
                sat = ephem.readtle(sat_name, *self.satellites[sat_name])
                obs = self._make_observer()
                t = p["rise_ephem"]
                while t <= p["set_ephem"]:
                    obs.date = t
                    sat.compute(obs)
                    # Convertir ephem date a UTC datetime string para tooltip
                    dt_utc = ephem.Date(t).datetime().replace(tzinfo=timezone.utc)
                    time_str = dt_utc.strftime("%Y-%b-%d %H:%M")
                    track.append((sat.az * DEG, sat.alt * DEG, time_str))
                    t += 10.0 / 86400
            except Exception as e:
                self.root.after(0, lambda e=e: self.log(f"Error calculando track: {e}", "err"))
            p["track"] = track

        self.sat_passes = passes
        self.pass_index = 0
        self.root.after(0, self._show_current_pass)

    def _show_current_pass(self):
        """Muestra en el mapa el pase indicado por pass_index."""
        if not self.sat_passes:
            return
        if self.pass_index >= len(self.sat_passes):
            self.pass_index = 0
        idx = self.pass_index
        p   = self.sat_passes[idx]
        self.future_track = p.get("track", [])
        self.sentido = p["sentido"]

        rise_time = self.fmt_time(p["rise_time"])
        set_time  = self.fmt_hms(p["set_time"])
        arrow     = "↻" if p["sentido"] == "Horario" else "↺"
        tz_lbl    = "UTC" if self.cfg.get("use_utc", True) else "LOC"

        # Contador arriba del mapa
        self.lbl_pass_counter.config(text=f"Pase {idx+1}/{len(self.sat_passes)}")

        # Info del pase → al log
        self.log(
            f"Pase {idx+1}: SALE Az={p['rise_az']:.0f}°  {rise_time} {tz_lbl}  "
            f"ENTRA Az={p['set_az']:.0f}°  {set_time}  "
            f"El.max={p['max_el']:.0f}°  {arrow}{p['sentido']}  "
            f"Dur={p['duration_s']//60}m{p['duration_s']%60:02d}s", "ok")

        # Rellenar los 5 campos de telemetría con el primer punto del pase
        az0  = p["rise_az"]
        el0  = 0.0          # en el horizonte al salir
        sent = f"{arrow} {p['sentido']}"

        # AZ MOTOR: calcular según sentido igual que en el tracking real
        # v0 es el azimut de salida, en el primer instante vf=v0 → motor=180
        az_motor = 180.0

        self._telem_labels["lbl_az"].config(
            text=f"{az0:.1f}°", fg=self.C["text"])
        self._telem_labels["lbl_el"].config(
            text=f"{el0:.1f}°", fg=self.C["muted"])
        self._telem_labels["lbl_sentido"].config(
            text=sent, fg=self.C["text"])
        self._telem_labels["lbl_az_mot"].config(
            text=f"{az_motor:.0f}°", fg=self.C["text"])
        self._telem_labels["lbl_el_mot"].config(
            text=f"{el0:.0f}°", fg=self.C["muted"])

        self._draw_polar()

    def _next_pass(self):
        if not self.sat_passes:
            return
        self.pass_index = (self.pass_index + 1) % len(self.sat_passes)
        self._show_current_pass()

    def _prev_pass(self):
        if not self.sat_passes:
            return
        self.pass_index = (self.pass_index - 1) % len(self.sat_passes)
        self._show_current_pass()

    # ── Tabla de próximos pasos ──────────────────────────────

    def _calc_all_passes(self):
        """Calcula los pasos de todos los satélites en las próximas 48h."""
        if not EPHEM_OK:
            messagebox.showerror("Error", "ephem no instalado.\npip install ephem")
            return
        if not self.satellites:
            messagebox.showwarning("Aviso", "No hay satélites cargados")
            return

        # Detener cálculo anterior
        self.table_stop = True
        time.sleep(0.1)
        self.table_stop = False

        # Limpiar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.table_passes = []
        self.lbl_table_status.config(text="⟳ Calculando...")

        self.table_calc_thread = threading.Thread(
            target=self._calc_all_passes_worker, daemon=True)
        self.table_calc_thread.start()

    def _calc_all_passes_worker(self):
        total = len(self.satellites)
        done  = 0
        min_el = self.min_el_var.get()
        hours  = HORAS_TABLA

        obs_lat  = self.cfg.get("obs_lat",  OBS_LAT)
        obs_lon  = self.cfg.get("obs_lon",  OBS_LON)
        obs_elev = int(self.cfg.get("obs_elev", OBS_ELEV))

        all_passes = []

        for sat_name, (l1, l2) in list(self.satellites.items()):
            if self.table_stop:
                break
            passes = compute_next_passes(
                sat_name, l1, l2,
                obs_lat, obs_lon, obs_elev,
                hours=hours, min_el=min_el)
            all_passes.extend(passes)
            done += 1
            status = f"⟳ {done}/{total}  ({sat_name[:20]})"
            self.root.after(0, lambda s=status:
                            self.lbl_table_status.config(text=s))

        # Ordenar por hora de subida
        all_passes.sort(key=lambda p: p["rise_time"])
        self.table_passes = all_passes

        self.root.after(0, self._populate_table)

    def _populate_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        now = datetime.now(timezone.utc)

        for p in self.table_passes:
            rise  = self.fmt_time(p["rise_time"])
            maxT  = self.fmt_hms(p["max_time"])
            setT  = self.fmt_hms(p["set_time"])
            dur   = f"{p['duration_s']//60}m{p['duration_s']%60:02d}s"
            maxEl = p["max_el"]
            sent  = "↻ Hor." if p["sentido"] == "Horario" else "↺ Anti."

            # Color según elevación
            if p["rise_time"] < now:
                tag = "past"
            elif maxEl >= 45:
                tag = "high"
            elif maxEl >= 20:
                tag = "medium"
            else:
                tag = "low"

            self.tree.insert('', tk.END,
                values=(p["sat_name"],
                        rise,
                        f"{p['rise_az']:.0f}°",
                        maxT,
                        f"{maxEl:.1f}°",
                        setT,
                        f"{p['set_az']:.0f}°",
                        dur,
                        sent),
                tags=(tag,))

        count = len(self.table_passes)
        self.lbl_table_status.config(
            text=f"✓ {count} pasos en {HORAS_TABLA}h  —  doble clic para seguir")

    def _sort_table(self, col: str):
        """Ordena la tabla por columna."""
        data = [(self.tree.set(child, col), child)
                for child in self.tree.get_children('')]
        try:
            data.sort(key=lambda x: float(x[0].replace('°','').replace('m','').replace('s','')))
        except ValueError:
            data.sort()
        for idx, (_, child) in enumerate(data):
            self.tree.move(child, '', idx)

    def _track_from_table(self):
        """Inicia el seguimiento del satélite seleccionado en la tabla."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un pase en la tabla primero")
            return
        values = self.tree.item(sel[0])['values']
        sat_name = values[0]

        if sat_name not in self.satellites:
            messagebox.showerror("Error", f"'{sat_name}' no está en tu lista")
            return

        # Seleccionar en la listbox de seguimiento
        self.selected_sat = sat_name
        self.pass_track   = []
        self.future_track = []
        self.sentido      = ""

        # Actualizar la listbox
        for i in range(self.sat_listbox.size()):
            if self.sat_listbox.get(i) == sat_name:
                self.sat_listbox.selection_clear(0, tk.END)
                self.sat_listbox.selection_set(i)
                self.sat_listbox.see(i)
                break

        # Ir a la pestaña de seguimiento y calcular trayectoria
        self.nb.select(0)
        self.log(f"Seleccionado desde tabla: {sat_name}", "info")
        self._calc_single_pass()

    # ── Gestión de satélites ─────────────────────────────────

    def _add_satellite_dialog(self):
        """Abre ventana emergente para añadir satélite."""
        win = tk.Toplevel(self.root)
        win.title("Añadir satélite")
        win.geometry("520x480")
        win.configure(bg=self.C["bg"])
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="AÑADIR SATÉLITE",
                 font=("Courier New", 12, "bold"),
                 fg=self.C["accent"], bg=self.C["bg"]).pack(pady=10)

        nb2 = ttk.Notebook(win)
        nb2.pack(fill=tk.BOTH, expand=True, padx=10)

        # Por nombre
        t1 = tk.Frame(nb2, bg=self.C["panel"]); nb2.add(t1, text=" Por nombre ")
        tk.Label(t1, text="Nombre (ej: ISS, AO-73, FUNCUBE):",
                 font=("Courier New", 9), fg=self.C["muted"], bg=self.C["panel"]).pack(anchor=tk.W, padx=10, pady=(10,2))
        v_name = tk.StringVar()
        e1 = tk.Entry(t1, textvariable=v_name, font=("Courier New", 10),
                      bg=self.C["border2"], fg=self.C["text"],
                      insertbackground=self.C["accent"], relief=tk.FLAT, bd=4)
        e1.pack(fill=tk.X, padx=10, pady=4)
        e1.focus_set()

        # Por NORAD
        t2 = tk.Frame(nb2, bg=self.C["panel"]); nb2.add(t2, text=" Por NORAD ")
        tk.Label(t2, text="Número NORAD (ej: 25544 para ISS):",
                 font=("Courier New", 9), fg=self.C["muted"], bg=self.C["panel"]).pack(anchor=tk.W, padx=10, pady=(10,2))
        v_norad = tk.StringVar()
        tk.Entry(t2, textvariable=v_norad, font=("Courier New", 10),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"], relief=tk.FLAT, bd=4).pack(fill=tk.X, padx=10, pady=4)

        # Por URL
        t3 = tk.Frame(nb2, bg=self.C["panel"]); nb2.add(t3, text=" Por URL ")
        tk.Label(t3, text="URL del archivo TLE:",
                 font=("Courier New", 9), fg=self.C["muted"], bg=self.C["panel"]).pack(anchor=tk.W, padx=10, pady=(10,2))
        v_url = tk.StringVar(value="https://celestrak.org/pub/TLE/amateur.txt")
        tk.Entry(t3, textvariable=v_url, font=("Courier New", 8),
                 bg=self.C["border2"], fg=self.C["text"],
                 insertbackground=self.C["accent"], relief=tk.FLAT, bd=4).pack(fill=tk.X, padx=10, pady=4)
        for name, url in list(CELESTRAK_GROUPS.items())[:4]:
            tk.Button(t3, text=f"  {name}", command=lambda u=url: v_url.set(u),
                      font=("Courier New", 8), fg=self.C["muted"], bg=self.C["panel"],
                      relief=tk.FLAT, bd=0, anchor=tk.W, cursor="hand2").pack(fill=tk.X, padx=10)

        # TLE manual
        t4 = tk.Frame(nb2, bg=self.C["panel"]); nb2.add(t4, text=" TLE manual ")
        tk.Label(t4, text="Pega las 3 líneas TLE:",
                 font=("Courier New", 9), fg=self.C["muted"], bg=self.C["panel"]).pack(anchor=tk.W, padx=10, pady=(10,2))
        v_manual = tk.Text(t4, height=5, font=("Courier New", 9),
                           bg=self.C["border2"], fg=self.C["text"],
                           insertbackground=self.C["accent"], relief=tk.FLAT, bd=4)
        v_manual.pack(fill=tk.X, padx=10, pady=4)

        # Resultados
        tk.Label(win, text="Resultados:", font=("Courier New", 8),
                 fg=self.C["muted"], bg=self.C["bg"]).pack(anchor=tk.W, padx=10)
        res_lb = tk.Listbox(win, height=5, font=("Courier New", 9),
                            bg=self.C["grid"], fg=self.C["text"],
                            selectbackground=self.C["accent2"],
                            relief=tk.FLAT, bd=0)
        res_lb.pack(fill=tk.X, padx=10)
        res_data = {}

        def do_search():
            tab = nb2.index(nb2.select())
            res_lb.delete(0, tk.END)
            res_lb.insert(tk.END, "⟳ Buscando...")
            win.update()

            def worker():
                if tab == 0:
                    result = search_celestrak_by_name(v_name.get().strip())
                elif tab == 1:
                    result = search_celestrak_by_norad(v_norad.get().strip())
                elif tab == 2:
                    text = download_url(v_url.get().strip())
                    result = parse_tle_text(text) if text else {}
                else:
                    result = parse_tle_text(v_manual.get(1.0, tk.END))

                res_data.clear()
                res_data.update(result)

                def show():
                    res_lb.delete(0, tk.END)
                    if result:
                        for n in sorted(result.keys()):
                            res_lb.insert(tk.END, n)
                        self.log(f"Encontrados {len(result)} satélites", "ok")
                    else:
                        res_lb.insert(tk.END, "(Sin resultados)")
                        self.log("Sin resultados", "warn")
                win.after(0, show)

            threading.Thread(target=worker, daemon=True).start()

        def do_add():
            sel = res_lb.curselection()
            if not sel:
                messagebox.showwarning("Aviso", "Selecciona un satélite del resultado", parent=win)
                return
            name = res_lb.get(sel[0])
            if name in res_data:
                self.satellites[name] = res_data[name]
                self._save_satellites()
                self._populate_all_lists()
                self.log(f"✓ Añadido: {name}", "ok")
                win.destroy()

        def do_add_all():
            if not res_data:
                return
            for n, t in res_data.items():
                self.satellites[n] = t
            self._save_satellites()
            self._populate_all_lists()
            self.log(f"✓ Añadidos {len(res_data)} satélites", "ok")
            win.destroy()

        btn_row = tk.Frame(win, bg=self.C["bg"])
        btn_row.pack(fill=tk.X, padx=10, pady=8)
        tk.Button(btn_row, text="🔍 Buscar", command=do_search,
                  font=("Courier New", 9, "bold"), fg=self.C["accent"],
                  bg=self.C["border2"], relief=tk.FLAT, bd=0,
                  padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="➕ Añadir seleccionado", command=do_add,
                  font=("Courier New", 9, "bold"), fg=self.C["green"],
                  bg=self.C["border"], relief=tk.FLAT, bd=0,
                  padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="➕ Añadir todos", command=do_add_all,
                  font=("Courier New", 9, "bold"), fg=self.C["yellow"],
                  bg=self.C["border"], relief=tk.FLAT, bd=0,
                  padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Cerrar", command=win.destroy,
                  font=("Courier New", 9), fg=self.C["muted"],
                  bg=self.C["border"], relief=tk.FLAT, bd=0,
                  padx=10, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=4)

    def _remove_satellite(self):
        sel = self.manage_listbox.curselection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un satélite para quitar")
            return
        name = self.manage_listbox.get(sel[0])
        if messagebox.askyesno("Confirmar",
                                f"¿Quitar '{name}' de tu lista?"):
            del self.satellites[name]
            self._save_satellites()
            self._populate_all_lists()
            self.log(f"Quitado: {name}", "warn")

    def _update_selected_tles(self):
        sel = self.manage_listbox.curselection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona uno o más satélites")
            return
        names = [self.manage_listbox.get(i) for i in sel]
        threading.Thread(target=self._update_tles_worker,
                         args=(names,), daemon=True).start()

    def _update_all_tles(self):
        names = list(self.satellites.keys())
        threading.Thread(target=self._update_tles_worker,
                         args=(names,), daemon=True).start()

    def _update_tles_worker(self, names: list):
        self.root.after(0, lambda: self.log(
            f"Actualizando TLEs de {len(names)} satélites...", "info"))
        updated = 0
        for name in names:
            l1, _ = self.satellites[name]
            norad  = get_norad_from_tle_line(l1)
            result = search_celestrak_by_norad(norad)
            if result:
                for new_name, (new_l1, new_l2) in result.items():
                    # Mantener el nombre original del usuario
                    self.satellites[name] = (new_l1, new_l2)
                    updated += 1
                    self.root.after(0, lambda n=name:
                        self.log(f"✓ TLE actualizado: {n}", "ok"))
            else:
                self.root.after(0, lambda n=name:
                    self.log(f"⚠ No encontrado en Celestrak: {n}", "warn"))

        self._save_satellites()
        self.root.after(0, self._populate_all_lists)
        self.root.after(0, lambda u=updated, t=len(names):
            self.log(f"Actualización completada: {u}/{t} satélites", "ok"))

        # Recalcular pases del satelite seleccionado si tiene TLEs actualizados
        if (self.selected_sat and self.selected_sat in self.satellites
                and not is_horizons_object(self.selected_sat)):
            self.root.after(0, lambda: threading.Thread(
                target=self._load_sat_passes, daemon=True).start())

    def _search_by_name(self):
        name = self.name_search_var.get().strip()
        if not name:
            return
        self.log(f"Buscando '{name}' en Celestrak...", "info")
        threading.Thread(target=self._do_search,
                         args=(lambda: search_celestrak_by_name(name),),
                         daemon=True).start()

    def _search_by_norad(self):
        norad = self.norad_search_var.get().strip()
        if not norad:
            return
        self.log(f"Buscando NORAD {norad} en Celestrak...", "info")
        threading.Thread(target=self._do_search,
                         args=(lambda: search_celestrak_by_norad(norad),),
                         daemon=True).start()

    def _search_by_url(self):
        url = self.url_search_var.get().strip()
        if not url:
            return
        self.log(f"Descargando TLEs de {url}...", "info")
        def _worker():
            text = download_url(url)
            if text:
                return parse_tle_text(text)
            return {}
        threading.Thread(target=self._do_search,
                         args=(_worker,), daemon=True).start()

    def _do_search(self, search_fn):
        result = search_fn()
        self.root.after(0, lambda r=result: self._show_search_results(r))

    def _show_search_results(self, result: dict):
        self._search_results = result
        self.search_listbox.delete(0, tk.END)
        if result:
            for name in sorted(result.keys()):
                self.search_listbox.insert(tk.END, name)
            self.log(f"Encontrados {len(result)} satélites", "ok")
        else:
            self.search_listbox.insert(tk.END, "(Sin resultados)")
            self.log("No se encontraron satélites", "warn")

    def _add_from_search(self):
        sel = self.search_listbox.curselection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un satélite del resultado")
            return
        name = self.search_listbox.get(sel[0])
        if name in self._search_results:
            self.satellites[name] = self._search_results[name]
            self._save_satellites()
            self._populate_all_lists()
            self.log(f"✓ Añadido: {name}", "ok")

    def _add_all_from_search(self):
        if not self._search_results:
            return
        for name, tles in self._search_results.items():
            self.satellites[name] = tles
        self._save_satellites()
        self._populate_all_lists()
        self.log(f"✓ Añadidos {len(self._search_results)} satélites", "ok")

    def _add_manual_tle(self):
        text = self.manual_tle_text.get(1.0, tk.END)
        result = parse_tle_text(text)
        if result:
            for name, tles in result.items():
                self.satellites[name] = tles
            self._save_satellites()
            self._populate_all_lists()
            self.log(f"✓ Añadido manualmente: {list(result.keys())[0]}", "ok")
        else:
            messagebox.showerror("Error",
                "TLE inválido. Asegúrate de poner:\n"
                "NOMBRE\n1 XXXXX...\n2 XXXXX...")

    def _import_tle_file(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo TLE",
            filetypes=[("TLE files", "*.tle *.txt"), ("All files", "*.*")])
        if path:
            text = Path(path).read_text(encoding='utf-8', errors='ignore')
            result = parse_tle_text(text)
            if result:
                self.satellites.update(result)
                self._save_satellites()
                self._populate_all_lists()
                self.log(f"✓ Importados {len(result)} satélites de {Path(path).name}", "ok")
            else:
                messagebox.showerror("Error", "No se encontraron TLEs válidos en el archivo")

    def _export_tle_file(self):
        path = filedialog.asksaveasfilename(
            title="Guardar mis satélites",
            defaultextension=".tle",
            filetypes=[("TLE files", "*.tle"), ("All files", "*.*")])
        if path:
            save_tle_file(self.satellites, Path(path))
            self.log(f"✓ Exportados {len(self.satellites)} satélites a {Path(path).name}", "ok")

    # ── Configuración ────────────────────────────────────────

    def _locator_to_latlon(self):
        """Convierte el locator del campo a lat/lon y actualiza los campos."""
        loc = self._locator_var.get().strip()
        lat, lon = locator_to_latlon(loc)
        if lat is not None:
            self._obs_vars["obs_lat"].set(str(lat))
            self._obs_vars["obs_lon"].set(str(lon))
            self.log(f"Locator {loc.upper()} → Lat={lat} Lon={lon}", "ok")
        else:
            self.log(f"Locator inválido: {loc}", "err")

    def _latlon_to_locator(self):
        """Convierte lat/lon de los campos a locator y actualiza el campo."""
        lat = self._obs_vars["obs_lat"].get()
        lon = self._obs_vars["obs_lon"].get()
        loc = latlon_to_locator(lat, lon)
        if loc:
            self._locator_var.set(loc)
            self.log(f"Lat={lat} Lon={lon} → Locator {loc}", "ok")
        else:
            self.log("Coordenadas inválidas para locator", "err")

    def _save_observer(self):
        self.cfg["obs_lat"]   = self._obs_vars["obs_lat"].get()
        self.cfg["obs_lon"]   = self._obs_vars["obs_lon"].get()
        self.cfg["obs_elev"]  = self._obs_vars["obs_elev"].get()
        self.cfg["obs_name"]  = self._obs_name_var.get().strip()
        self.cfg["callsign"]  = self._call_var.get().strip().upper()
        self.cfg["use_utc"]   = self._utc_var.get()
        save_config(self.cfg)
        # Actualizar barra superior con indicativo
        callsign = self.cfg["callsign"]
        loc_txt  = self.cfg["obs_lat"] + " " + self.cfg["obs_lon"]
        self.lbl_callsign.config(
            text=f"{callsign}  {loc_txt}" if callsign else loc_txt)
        self.log(f"Ubicación guardada: {self.cfg['obs_lat']} {self.cfg['obs_lon']}", "ok")
        lat  = self.cfg['obs_lat']
        lon  = self.cfg['obs_lon']
        elev = self.cfg['obs_elev']
        msg  = f"Ubicacion guardada:\nLatitud:  {lat}\nLongitud: {lon}\nElevacion:{elev} m"
        messagebox.showinfo("Guardado", msg)

    def run(self):
        self.root.mainloop()


# =============================================================
#   M A I N
# =============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app  = App(root)
    app.run()