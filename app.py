import streamlit as st
import pandas as pd
import numpy as np
import time
import json
import re
import requests
import zipfile
from io import BytesIO
import random

# Intentar importar folium y streamlit_folium
try:
    import folium
    from folium.plugins import MarkerCluster, Geocoder
    from streamlit_folium import folium_static
    folium_disponible = True
except ImportError:
    folium_disponible = False

# Configuración de la página
st.set_page_config(
    page_title="Buscador de Campos",
    page_icon="📍",
    layout="wide"
)

# Configuraciones globales
API_BASE_URL = "https://aps.senasa.gob.ar/restapiprod/servicios/renspa"
TIEMPO_ESPERA = 0.5

# CSS personalizado para mobile
st.markdown("""
<style>
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Estilos mobile-friendly */
    .stButton > button {
        width: 100%;
        background-color: #1a1a1a;
        color: white;
        border: none;
        padding: 15px;
        font-size: 18px;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    .stTextInput > div > div > input {
        font-size: 16px;
        padding: 10px;
        border-radius: 8px;
        background-color: #2a2a2a;
        color: white;
        border: 1px solid #444;
    }
    
    /* Fondo oscuro */
    .main {
        background-color: #0e0e0e;
        color: white;
    }
    
    /* Título centrado */
    h1 {
        text-align: center;
        font-size: 24px;
        margin-bottom: 20px;
    }
    
    /* Tabs personalizados */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #1a1a1a;
        border-radius: 10px;
        padding: 5px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #888;
        border-radius: 8px;
        padding: 10px;
        font-size: 14px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #333;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown("<h1>📍 Encontrá donde trabaja el productor</h1>", unsafe_allow_html=True)

# Función para normalizar CUIT
def normalizar_cuit(cuit):
    """Normaliza un CUIT a formato XX-XXXXXXXX-X"""
    cuit_limpio = cuit.replace("-", "")
    
    if len(cuit_limpio) != 11:
        raise ValueError(f"CUIT inválido: {cuit}. Debe tener 11 dígitos.")
    
    return f"{cuit_limpio[:2]}-{cuit_limpio[2:10]}-{cuit_limpio[10]}"

# Función para obtener datos por CUIT
def obtener_datos_por_cuit(cuit):
    """Obtiene todos los campos asociados a un CUIT"""
    try:
        url_base = f"{API_BASE_URL}/consultaPorCuit"
        
        todos_campos = []
        offset = 0
        limit = 10
        has_more = True
        
        while has_more:
            url = f"{url_base}?cuit={cuit}&offset={offset}"
            
            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                resultado = response.json()
                
                if 'items' in resultado and resultado['items']:
                    todos_campos.extend(resultado['items'])
                    has_more = resultado.get('hasMore', False)
                    offset += limit
                else:
                    has_more = False
            
            except Exception as e:
                has_more = False
                
            time.sleep(TIEMPO_ESPERA)
        
        return todos_campos
    
    except Exception as e:
        return []

# Función para extraer coordenadas
def extraer_coordenadas(poligono_str):
    """Extrae coordenadas de un string de polígono"""
    if not poligono_str or not isinstance(poligono_str, str):
        return None
    
    coord_pattern = r'\(([-\d\.]+),([-\d\.]+)\)'
    coord_pairs = re.findall(coord_pattern, poligono_str)
    
    if not coord_pairs:
        return None
    
    coords_geojson = []
    for lat_str, lon_str in coord_pairs:
        try:
            lat = float(lat_str)
            lon = float(lon_str)
            coords_geojson.append([lon, lat])
        except ValueError:
            continue
    
    if len(coords_geojson) >= 3:
        if coords_geojson[0] != coords_geojson[-1]:
            coords_geojson.append(coords_geojson[0])
        
        return coords_geojson
    
    return None

# Función para crear mapa optimizado para mobile
def crear_mapa_mobile(poligonos, center=None, cuit_colors=None):
    """Crea un mapa folium optimizado para móvil"""
    if not folium_disponible:
        st.warning("Para visualizar mapas, instala folium y streamlit-folium")
        return None
    
    # Determinar centro del mapa
    if center:
        center_lat, center_lon = center
    elif poligonos:
        center_lat = poligonos[0]['coords'][0][1]
        center_lon = poligonos[0]['coords'][0][0]
    else:
        center_lat = -34.603722
        center_lon = -58.381592
    
    # Crear mapa base con controles simplificados
    m = folium.Map(
        location=[center_lat, center_lon], 
        zoom_start=10,
        zoom_control=False,  # Desactivar controles de zoom
        attributionControl=False,
        prefer_canvas=True
    )
    
    # Añadir capas base
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                    name='Satélite', 
                    attr='Google').add_to(m)
    folium.TileLayer('OpenStreetMap', name='Mapa').add_to(m)
    
    # Colores disponibles (evitando el verde)
    colores_disponibles = ['#FF4444', '#4444FF', '#FF8800', '#AA00FF', '#FF00AA', '#00AAFF']
    
    # Añadir polígonos
    for i, pol in enumerate(poligonos):
        # Determinar color
        if cuit_colors and 'cuit' in pol and pol['cuit'] in cuit_colors:
            color = cuit_colors[pol['cuit']]
        else:
            color = colores_disponibles[i % len(colores_disponibles)]
        
        # Información del popup simplificada
        popup_text = f"""
        <div style='font-family: Arial; font-size: 14px;'>
        <b>Campo:</b> {pol.get('titular', 'Sin información')}<br>
        <b>Localidad:</b> {pol.get('localidad', 'Sin información')}<br>
        <b>Superficie:</b> {pol.get('superficie', 0):.1f} ha
        </div>
        """
        
        # Añadir polígono
        folium.Polygon(
            locations=[[coord[1], coord[0]] for coord in pol['coords']],
            color=color,
            weight=3,
            fill=True,
            fill_color=color,
            fill_opacity=0.4,
            popup=folium.Popup(popup_text, max_width=200)
        ).add_to(m)
    
    # Añadir buscador de localidades
    Geocoder(
        collapsed=True,
        position='topleft',
        add_marker=False,
        placeholder='Buscar localidad...'
    ).add_to(m)
    
    # Control de capas en posición derecha
    folium.LayerControl(position='topright', collapsed=False).add_to(m)
    
    return m

# Crear tabs
tab1, tab2 = st.tabs(["🔍 Buscar por CUIT", "📋 Lista de CUITs"])

with tab1:
    cuit_input = st.text_input("Ingresá el CUIT del productor:", 
                              placeholder="30-12345678-9", 
                              key="cuit_single")

    if st.button("🔍 Buscar Campos", key="btn_buscar"):
        if cuit_input:
            try:
                cuit_normalizado = normalizar_cuit(cuit_input)
                
                with st.spinner('Buscando información...'):
                    campos = obtener_datos_por_cuit(cuit_normalizado)
                    
                    if not campos:
                        st.error("No se encontraron campos para este CUIT")
                        st.stop()
                    
                    # Filtrar solo campos activos
                    campos_activos = [c for c in campos if c.get('fecha_baja') is None]
                    
                    if not campos_activos:
                        st.warning("No hay campos activos para este CUIT")
                        st.stop()
                    
                    # Procesar polígonos
                    poligonos = []
                    for campo in campos_activos:
                        if 'poligono' in campo and campo['poligono']:
                            coords = extraer_coordenadas(campo['poligono'])
                            if coords:
                                poligonos.append({
                                    'coords': coords,
                                    'titular': campo.get('titular', ''),
                                    'localidad': campo.get('localidad', ''),
                                    'superficie': campo.get('superficie', 0),
                                    'cuit': cuit_normalizado
                                })
                    
                    if poligonos:
                        st.success(f"Se encontraron {len(poligonos)} campos activos")
                        
                        # Mostrar mapa
                        mapa = crear_mapa_mobile(poligonos)
                        if mapa:
                            folium_static(mapa, width=None, height=500)
                        
                        # Botón de descarga
                        if st.button("📥 Descargar KML", key="download_kml"):
                            # Crear KML
                            kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>Campos del productor</name>
  <Style id="redPoly">
    <LineStyle>
      <color>ff0000ff</color>
      <width>3</width>
    </LineStyle>
    <PolyStyle>
      <color>7f0000ff</color>
    </PolyStyle>
  </Style>
"""
                            
                            for pol in poligonos:
                                kml_content += f"""
  <Placemark>
    <name>{pol['titular']}</name>
    <description>Localidad: {pol['localidad']} - Superficie: {pol['superficie']:.1f} ha</description>
    <styleUrl>#redPoly</styleUrl>
    <Polygon>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>
"""
                                for coord in pol['coords']:
                                    kml_content += f"{coord[0]},{coord[1]},0\n"
                                
                                kml_content += """
          </coordinates>
        </LinearRing>
      </outerBoundaryIs>
    </Polygon>
  </Placemark>
"""
                            
                            kml_content += "</Document></kml>"
                            
                            # Crear KMZ
                            kmz_buffer = BytesIO()
                            with zipfile.ZipFile(kmz_buffer, 'w', zipfile.ZIP_DEFLATED) as kmz:
                                kmz.writestr("doc.kml", kml_content)
                            
                            kmz_buffer.seek(0)
                            
                            st.download_button(
                                label="💾 Guardar archivo KML",
                                data=kmz_buffer,
                                file_name=f"campos_{cuit_normalizado.replace('-', '')}.kmz",
                                mime="application/vnd.google-earth.kmz",
                            )
                    else:
                        st.warning("No se pudieron obtener las ubicaciones de los campos")
                        
            except ValueError as e:
                st.error("CUIT inválido. Verificá el formato.")
        else:
            st.warning("Por favor, ingresá un CUIT")

with tab2:
    st.write("Podés buscar múltiples productores a la vez")
    
    cuits_input = st.text_area(
        "Ingresá los CUITs (uno por línea):", 
        placeholder="30-12345678-9\n20-87654321-0",
        height=150,
        key="cuits_input"
    )
    
    if st.button("🔍 Buscar Todos", key="btn_buscar_multi"):
        if cuits_input:
            cuit_list = [line.strip() for line in cuits_input.split('\n') if line.strip()]
            
            if cuit_list:
                # Colores para diferentes CUITs
                colores = ['#FF4444', '#4444FF', '#FF8800', '#AA00FF', '#FF00AA', '#00AAFF']
                cuit_colors = {}
                
                todos_poligonos = []
                cuits_procesados = 0
                
                with st.spinner('Procesando...'):
                    progress_bar = st.progress(0)
                    
                    for i, cuit in enumerate(cuit_list):
                        try:
                            cuit_normalizado = normalizar_cuit(cuit)
                            cuit_colors[cuit_normalizado] = colores[i % len(colores)]
                            
                            campos = obtener_datos_por_cuit(cuit_normalizado)
                            campos_activos = [c for c in campos if c.get('fecha_baja') is None]
                            
                            for campo in campos_activos:
                                if 'poligono' in campo and campo['poligono']:
                                    coords = extraer_coordenadas(campo['poligono'])
                                    if coords:
                                        todos_poligonos.append({
                                            'coords': coords,
                                            'titular': campo.get('titular', ''),
                                            'localidad': campo.get('localidad', ''),
                                            'superficie': campo.get('superficie', 0),
                                            'cuit': cuit_normalizado
                                        })
                            
                            cuits_procesados += 1
                            progress_bar.progress((i + 1) / len(cuit_list))
                            
                        except Exception as e:
                            continue
                        
                        time.sleep(TIEMPO_ESPERA)
                    
                    if todos_poligonos:
                        st.success(f"Se encontraron {len(todos_poligonos)} campos en total")
                        
                        # Mostrar mapa
                        mapa = crear_mapa_mobile(todos_poligonos, cuit_colors=cuit_colors)
                        if mapa:
                            folium_static(mapa, width=None, height=500)
                    else:
                        st.warning("No se encontraron campos para los CUITs ingresados")
        else:
            st.warning("Por favor, ingresá al menos un CUIT")
