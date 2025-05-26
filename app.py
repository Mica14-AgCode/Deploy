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
    from folium.plugins import MeasureControl, MiniMap, MarkerCluster
    from streamlit_folium import folium_static
    folium_disponible = True
except ImportError:
    folium_disponible = False

# Configuración de la página
st.set_page_config(
    page_title="VISU - Visualizador de Campos",
    page_icon="👁",
    layout="wide"
)

# Configuraciones globales
API_BASE_URL = "https://aps.senasa.gob.ar/restapiprod/servicios/renspa"
TIEMPO_ESPERA = 0.5

# CSS personalizado para mobile con logo VISU
st.markdown("""
<style>
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Logo VISU */
    .visu-logo-container {
        text-align: center;
        margin: 20px 0 30px 0;
        padding: 20px;
    }
    
    .minimal-container {
        display: inline-block;
        position: relative;
    }
    
    .visu-minimal {
        font-size: 60px;
        font-weight: 300;
        letter-spacing: 15px;
        color: #C0C0C0;
        margin-bottom: 10px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    .eye-underline {
        width: 100%;
        height: 3px;
        background: linear-gradient(90deg, transparent 0%, #00D2BE 20%, #00D2BE 80%, transparent 100%);
        position: relative;
    }
    
    .eye-dot {
        width: 15px;
        height: 15px;
        background: #00D2BE;
        border-radius: 50%;
        position: absolute;
        top: -6px;
        left: 50%;
        transform: translateX(-50%);
        box-shadow: 0 0 20px #00D2BE;
    }
    
    .tagline {
        font-size: 16px;
        color: #C0C0C0;
        letter-spacing: 2px;
        margin-top: 15px;
        font-weight: 300;
    }
    
    /* Estilos mobile-friendly */
    .stButton > button {
        width: 100%;
        background-color: #1a3a3a;
        color: white;
        border: none;
        padding: 15px;
        font-size: 18px;
        border-radius: 10px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: #00D2BE;
        box-shadow: 0 4px 15px rgba(0, 210, 190, 0.4);
    }
    
    .stTextInput > div > div > input {
        font-size: 16px;
        padding: 12px;
        border-radius: 8px;
        background-color: #1a2a2a;
        color: white;
        border: 1px solid #00D2BE;
    }
    
    .stTextArea > div > div > textarea {
        font-size: 16px;
        padding: 12px;
        border-radius: 8px;
        background-color: #1a2a2a;
        color: white;
        border: 1px solid #00D2BE;
    }
    
    /* Fondo oscuro */
    .main {
        background-color: #0a0a0a;
        color: white;
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
        background-color: #1a3a3a;
        color: #00D2BE;
    }
    
    /* Mensajes de éxito y error */
    .stSuccess {
        background-color: #0d2626;
        border: 1px solid #00D2BE;
        color: #00D2BE;
    }
    
    .stError {
        background-color: #2a1a1a;
        border: 1px solid #FF4444;
    }
    
    .stWarning {
        background-color: #2a2a1a;
        border: 1px solid #FF8800;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #00D2BE;
    }
    
    /* Estilos para las tarjetas de campos */
    .campo-card {
        background: linear-gradient(135deg, #1a3a3a 0%, #0d2626 100%);
        border: 1px solid #00D2BE;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0, 210, 190, 0.1);
    }
    
    .campo-title {
        color: #00D2BE;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    
    .campo-info {
        color: #C0C0C0;
        font-size: 14px;
        line-height: 1.6;
    }
    
    .superficie-badge {
        background-color: #00D2BE;
        color: #0a0a0a;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        display: inline-block;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Logo VISU con tagline
st.markdown("""
<div class="visu-logo-container">
    <div class="minimal-container">
        <div class="visu-minimal">VISU</div>
        <div class="eye-underline">
            <div class="eye-dot"></div>
        </div>
        <div class="tagline">Donde el agro deja de ser un misterio</div>
    </div>
</div>
""", unsafe_allow_html=True)

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

# Función para consultar detalles de un campo específico
def consultar_campo_detalle(renspa):
    """Consulta los detalles de un campo específico para obtener el polígono"""
    try:
        url = f"{API_BASE_URL}/consultaPorNumero?numero={renspa}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        return None

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

# Función para crear mapa mejorado
def crear_mapa_mejorado(poligonos, center=None, cuit_colors=None):
    """Crea un mapa folium mejorado con los polígonos proporcionados"""
    if not folium_disponible:
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
    
    # Crear mapa base
    m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
    
    # Añadir diferentes capas base
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                    name='Google Hybrid', 
                    attr='Google').add_to(m)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                    name='Google Satellite', 
                    attr='Google').add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    
    # Colores disponibles (evitando el verde)
    colores_disponibles = ['#FF4444', '#4444FF', '#FF8800', '#AA00FF', '#FF00AA', '#00AAFF']
    
    # Añadir cada polígono al mapa
    for i, pol in enumerate(poligonos):
        # Determinar color
        if cuit_colors and 'cuit' in pol and pol['cuit'] in cuit_colors:
            color = cuit_colors[pol['cuit']]
        else:
            color = colores_disponibles[i % len(colores_disponibles)]
        
        # Formatear popup con información
        popup_text = f"""
        <b>Campo:</b> {pol.get('titular', 'No disponible')}<br>
        <b>Localidad:</b> {pol.get('localidad', 'No disponible')}<br>
        <b>Superficie:</b> {pol.get('superficie', 0)} ha
        """
        if 'cuit' in pol:
            popup_text += f"<br><b>CUIT:</b> {pol['cuit']}"
        
        # Añadir polígono al mapa
        folium.Polygon(
            locations=[[coord[1], coord[0]] for coord in pol['coords']],
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.3,
            tooltip=f"Campo: {pol.get('titular', 'Sin información')}",
            popup=popup_text
        ).add_to(m)
    
    # Añadir control de capas
    folium.LayerControl(position='topright').add_to(m)
    
    return m

# Función para mostrar campos en tarjetas (cuando no hay mapa)
def mostrar_campos_tarjetas(campos_data):
    """Muestra los campos en formato de tarjetas"""
    for campo in campos_data:
        st.markdown(f"""
        <div class="campo-card">
            <div class="campo-title">📍 {campo.get('titular', 'Campo sin nombre')}</div>
            <div class="campo-info">
                <strong>Localidad:</strong> {campo.get('localidad', 'No especificada')}<br>
                <strong>Provincia:</strong> {campo.get('provincia', 'No especificada')}
            </div>
            <div class="superficie-badge">{campo.get('superficie', 0):.1f} hectáreas</div>
        </div>
        """, unsafe_allow_html=True)

# Función para generar link de Google Maps
def generar_link_google_maps(coords):
    """Genera un link para ver el polígono en Google Maps"""
    if not coords:
        return None
    
    # Usar el centro del polígono
    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    # Crear URL de Google Maps
    return f"https://www.google.com/maps/@{center_lat},{center_lon},15z"

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
                    poligonos_sin_coords = []
                    
                    for campo in campos_activos:
                        renspa = campo['renspa']
                        
                        # Primero intentar con los datos que ya tenemos
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
                                continue
                        
                        # Si no tenemos polígono, consultar detalle
                        resultado_detalle = consultar_campo_detalle(renspa)
                        
                        if resultado_detalle and 'items' in resultado_detalle and resultado_detalle['items']:
                            item_detalle = resultado_detalle['items'][0]
                            if 'poligono' in item_detalle and item_detalle['poligono']:
                                coords = extraer_coordenadas(item_detalle['poligono'])
                                if coords:
                                    poligonos.append({
                                        'coords': coords,
                                        'titular': campo.get('titular', ''),
                                        'localidad': campo.get('localidad', ''),
                                        'superficie': item_detalle.get('superficie', 0),
                                        'cuit': cuit_normalizado
                                    })
                                else:
                                    poligonos_sin_coords.append(campo)
                            else:
                                poligonos_sin_coords.append(campo)
                        else:
                            poligonos_sin_coords.append(campo)
                        
                        time.sleep(TIEMPO_ESPERA)
                    
                    # Mostrar resultados
                    if poligonos:
                        st.success(f"✅ Se encontraron {len(poligonos)} campos activos con ubicación")
                        
                        if poligonos_sin_coords:
                            st.info(f"ℹ️ {len(poligonos_sin_coords)} campos sin coordenadas disponibles")
                        
                        # Si folium está disponible, mostrar mapa
                        if folium_disponible:
                            st.subheader("📍 Visualización en mapa")
                            m = crear_mapa_mejorado(poligonos)
                            if m:
                                folium_static(m, width=None, height=500)
                        else:
                            # Si no hay mapa, mostrar tarjetas y links a Google Maps
                            st.subheader("📋 Información de los campos")
                            mostrar_campos_tarjetas(poligonos)
                            
                            st.subheader("🗺️ Ver en Google Maps")
                            for i, campo in enumerate(poligonos):
                                if 'coords' in campo:
                                    link = generar_link_google_maps(campo['coords'])
                                    if link:
                                        st.markdown(f"[📍 {campo['titular'] or f'Campo {i+1}'}]({link})")
                            
                            st.warning("Para visualizar mapas integrados, instala folium y streamlit-folium")
                        
                        # Botón de descarga KML
                        kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <n>Campos del productor</n>
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
    <n>{pol['titular']}</n>
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
                            label="📥 Descargar KML",
                            data=kmz_buffer,
                            file_name=f"campos_{cuit_normalizado.replace('-', '')}.kmz",
                            mime="application/vnd.google-earth.kmz",
                            help="Podés abrir este archivo en Google Earth"
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
                cuits_con_error = []
                
                with st.spinner('Procesando...'):
                    progress_bar = st.progress(0)
                    
                    for i, cuit in enumerate(cuit_list):
                        try:
                            cuit_normalizado = normalizar_cuit(cuit)
                            cuit_colors[cuit_normalizado] = colores[i % len(colores)]
                            
                            campos = obtener_datos_por_cuit(cuit_normalizado)
                            campos_activos = [c for c in campos if c.get('fecha_baja') is None]
                            
                            for campo in campos_activos:
                                # Intentar extraer polígono de los datos básicos
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
                                        continue
                                
                                # Si no hay polígono, consultar detalle
                                resultado_detalle = consultar_campo_detalle(campo['renspa'])
                                
                                if resultado_detalle and 'items' in resultado_detalle and resultado_detalle['items']:
                                    item_detalle = resultado_detalle['items'][0]
                                    if 'poligono' in item_detalle and item_detalle['poligono']:
                                        coords = extraer_coordenadas(item_detalle['poligono'])
                                        if coords:
                                            todos_poligonos.append({
                                                'coords': coords,
                                                'titular': campo.get('titular', ''),
                                                'localidad': campo.get('localidad', ''),
                                                'superficie': item_detalle.get('superficie', 0),
                                                'cuit': cuit_normalizado
                                            })
                                
                                time.sleep(TIEMPO_ESPERA)
                            
                            cuits_procesados += 1
                            progress_bar.progress((i + 1) / len(cuit_list))
                            
                        except Exception as e:
                            cuits_con_error.append(cuit)
                            continue
                    
                    # Mostrar resumen
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("CUITs procesados", cuits_procesados)
                    with col2:
                        st.metric("Campos encontrados", len(todos_poligonos))
                    with col3:
                        st.metric("Con errores", len(cuits_con_error))
                    
                    if todos_poligonos:
                        # Si folium está disponible, mostrar mapa
                        if folium_disponible:
                            st.subheader("📍 Visualización en mapa")
                            mapa = crear_mapa_mejorado(todos_poligonos, cuit_colors=cuit_colors)
                            if mapa:
                                folium_static(mapa, width=None, height=500)
                        else:
                            # Si no hay mapa, mostrar tarjetas agrupadas por CUIT
                            st.subheader("📋 Campos por productor")
                            cuits_unicos = list(set(c['cuit'] for c in todos_poligonos))
                            for cuit in cuits_unicos:
                                campos_cuit = [c for c in todos_poligonos if c['cuit'] == cuit]
                                with st.expander(f"CUIT: {cuit} ({len(campos_cuit)} campos)"):
                                    mostrar_campos_tarjetas(campos_cuit)
                            
                            st.warning("Para visualizar mapas integrados, instala folium y streamlit-folium")
                    else:
                        st.warning("No se encontraron campos para los CUITs ingresados")
        else:
            st.warning("Por favor, ingresá al menos un CUIT")
