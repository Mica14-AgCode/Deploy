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
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

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
        margin-left: 15px; /* Compensar el letter-spacing */
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
    
    /* Estilos para mejorar legibilidad en móvil */
    .stTextInput label {
        color: #E0E0E0 !important;
        font-size: 16px !important;
    }
    
    .stRadio label {
        color: #E0E0E0 !important;
        font-size: 16px !important;
    }
    
    .stTextArea label {
        color: #E0E0E0 !important;
        font-size: 16px !important;
    }
    
    p {
        color: #E0E0E0 !important;
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
    
    /* Fondo oscuro - Fix para mobile */
    .main {
        background-color: #0a0a0a !important;
        color: white !important;
    }
    
    .stApp {
        background-color: #0a0a0a !important;
    }
    
    [data-testid="stAppViewContainer"] {
        background-color: #0a0a0a !important;
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

# Función para crear mapa optimizado para mobile con leyenda mejorada
def crear_mapa_mobile(poligonos, center=None, cuit_colors=None):
    """Crea un mapa folium optimizado para móvil con leyenda desplegable"""
    if not folium_disponible:
        st.warning("Para visualizar mapas, instala folium y streamlit-folium con: pip install folium streamlit-folium")
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
    
    # Crear mapa base con controles de zoom visibles
    m = folium.Map(
        location=[center_lat, center_lon], 
        zoom_start=10,
        zoom_control=True,
        attributionControl=False,
        prefer_canvas=True
    )
    
    # Añadir capas base
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                    name='Satélite', 
                    attr='Google',
                    overlay=False,
                    control=True).add_to(m)
    folium.TileLayer('OpenStreetMap', 
                    name='Mapa',
                    overlay=False,
                    control=True).add_to(m)
    
    # Añadir MiniMap
    try:
        MiniMap(toggle_display=True).add_to(m)
    except:
        pass
    
    # Colores disponibles (evitando el verde)
    colores_base = ['#FF4444', '#4444FF', '#FF8800', '#AA00FF', '#FF00AA', '#00AAFF']
    
    # Crear grupos para campos activos e históricos
    fg_activos = folium.FeatureGroup(name='Campos Activos', show=True)
    fg_historicos = folium.FeatureGroup(name='Campos Históricos', show=True)
    
    # Agrupar polígonos por razón social y estado
    titulares_data = {}
    
    for i, pol in enumerate(poligonos):
        titular = pol.get('titular', 'Sin información')
        activo = pol.get('activo', True)
        cuit = pol.get('cuit', '')
        
        # Crear clave única para titular
        key = f"{titular}_{cuit}"
        
        if key not in titulares_data:
            # Asignar color base para este titular
            if cuit_colors and cuit in cuit_colors:
                color_base = cuit_colors[cuit]
            else:
                color_base = colores_base[len(titulares_data) % len(colores_base)]
            
            titulares_data[key] = {
                'titular': titular,
                'cuit': cuit,
                'color_base': color_base,
                'activos': [],
                'historicos': []
            }
        
        # Agregar polígono a la lista correspondiente
        if activo:
            titulares_data[key]['activos'].append(pol)
        else:
            titulares_data[key]['historicos'].append(pol)
    
    # Crear leyenda HTML mejorada
    leyenda_html = '''
    <div id='leyenda-campos' style='
        position: fixed;
        bottom: 30px;
        right: 10px;
        width: 280px;
        background-color: rgba(255, 255, 255, 0.95);
        border: 2px solid #00D2BE;
        border-radius: 10px;
        padding: 10px;
        font-size: 12px;
        z-index: 9999;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        max-height: 400px;
        overflow-y: auto;
    '>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
            <h4 style='margin: 0; color: #333;'>Leyenda</h4>
            <button onclick='toggleLeyenda()' style='
                background: none;
                border: none;
                font-size: 16px;
                cursor: pointer;
                color: #333;
            '>▼</button>
        </div>
        <div id='leyenda-content' style='display: block;'>
    '''
    
    # Añadir items a la leyenda
    for key, data in titulares_data.items():
        color_base = data['color_base']
        titular = data['titular']
        
        if data['activos']:
            leyenda_html += f'''
            <div style='margin: 5px 0;'>
                <span style='
                    display: inline-block;
                    width: 15px;
                    height: 15px;
                    background-color: {color_base};
                    border: 1px solid #333;
                    margin-right: 5px;
                    vertical-align: middle;
                '></span>
                <span style='color: #333; font-size: 11px;'>{titular} (Activo)</span>
            </div>
            '''
        
        if data['historicos']:
            # Color más claro para históricos
            color_historico = color_base + '66'  # Agregar transparencia
            leyenda_html += f'''
            <div style='margin: 5px 0;'>
                <span style='
                    display: inline-block;
                    width: 15px;
                    height: 15px;
                    background-color: {color_historico};
                    border: 1px dashed #333;
                    margin-right: 5px;
                    vertical-align: middle;
                '></span>
                <span style='color: #666; font-size: 11px;'>{titular} (Histórico)</span>
            </div>
            '''
    
    leyenda_html += '''
        </div>
    </div>
    <script>
    function toggleLeyenda() {
        var content = document.getElementById('leyenda-content');
        var button = event.target;
        if (content.style.display === 'none') {
            content.style.display = 'block';
            button.innerHTML = '▼';
        } else {
            content.style.display = 'none';
            button.innerHTML = '▶';
        }
    }
    </script>
    '''
    
    # Añadir polígonos al mapa
    for key, data in titulares_data.items():
        color_base = data['color_base']
        
        # Campos activos - color sólido
        for pol in data['activos']:
            popup_text = f"""
            <div style='font-family: Arial; font-size: 14px; color: #333;'>
            <b>Campo:</b> {pol.get('titular', 'Sin información')}<br>
            <b>Localidad:</b> {pol.get('localidad', 'Sin información')}<br>
            <b>Superficie:</b> {pol.get('superficie', 0):.1f} ha<br>
            <b>Estado:</b> Activo
            </div>
            """
            
            folium.Polygon(
                locations=[[coord[1], coord[0]] for coord in pol['coords']],
                color=color_base,
                weight=3,
                fill=True,
                fill_color=color_base,
                fill_opacity=0.5,
                popup=folium.Popup(popup_text, max_width=200)
            ).add_to(fg_activos)
        
        # Campos históricos - color con transparencia y borde punteado
        for pol in data['historicos']:
            popup_text = f"""
            <div style='font-family: Arial; font-size: 14px; color: #333;'>
            <b>Campo:</b> {pol.get('titular', 'Sin información')}<br>
            <b>Localidad:</b> {pol.get('localidad', 'Sin información')}<br>
            <b>Superficie:</b> {pol.get('superficie', 0):.1f} ha<br>
            <b>Estado:</b> Inactivo<br>
            <b>Trabajado hasta:</b> {pol.get('fecha_baja', 'No disponible')}
            </div>
            """
            
            folium.Polygon(
                locations=[[coord[1], coord[0]] for coord in pol['coords']],
                color=color_base,
                weight=2,
                fill=True,
                fill_color=color_base,
                fill_opacity=0.2,  # Menor opacidad para históricos
                dashArray='5, 5',  # Línea punteada
                popup=folium.Popup(popup_text, max_width=200)
            ).add_to(fg_historicos)
    
    # Añadir los grupos al mapa
    fg_activos.add_to(m)
    fg_historicos.add_to(m)
    
    # Control de capas en posición superior derecha con estilo desplegable
    folium.LayerControl(
        position='topright',
        collapsed=True,
        autoZIndex=True
    ).add_to(m)
    
    # Añadir la leyenda al mapa
    m.get_root().html.add_child(folium.Element(leyenda_html))
    
    return m

# Función para analizar hectáreas a lo largo del tiempo
def analizar_hectareas_tiempo(campos):
    """Analiza la evolución de hectáreas activas a lo largo del tiempo"""
    eventos = []
    
    for campo in campos:
        fecha_alta = campo.get('fecha_alta', None)
        fecha_baja = campo.get('fecha_baja', None)
        superficie = campo.get('superficie', 0)
        
        # Procesar fecha de alta
        if fecha_alta:
            try:
                # Intentar diferentes formatos de fecha
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        fecha = datetime.strptime(fecha_alta.split('T')[0], fmt)
                        eventos.append({
                            'fecha': fecha,
                            'tipo': 'alta',
                            'superficie': superficie
                        })
                        break
                    except:
                        continue
            except:
                pass
        
        # Procesar fecha de baja
        if fecha_baja:
            try:
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        fecha = datetime.strptime(fecha_baja.split('T')[0], fmt)
                        eventos.append({
                            'fecha': fecha,
                            'tipo': 'baja',
                            'superficie': superficie
                        })
                        break
                    except:
                        continue
            except:
                pass
    
    if not eventos:
        return None
    
    # Ordenar eventos por fecha
    eventos.sort(key=lambda x: x['fecha'])
    
    # Calcular superficie acumulada
    superficie_acumulada = 0
    fechas = []
    superficies = []
    
    for evento in eventos:
        if evento['tipo'] == 'alta':
            superficie_acumulada += evento['superficie']
        else:
            superficie_acumulada -= evento['superficie']
        
        fechas.append(evento['fecha'])
        superficies.append(superficie_acumulada)
    
    # Crear DataFrame
    df = pd.DataFrame({
        'Fecha': fechas,
        'Hectáreas': superficies
    })
    
    return df

# Crear tabs
tab1, tab2, tab3 = st.tabs(["🔍 Buscar por CUIT", "📋 Lista de CUITs", "📊 Gráfico"])

with tab1:
    cuit_input = st.text_input("Ingresá el CUIT del productor:", 
                              placeholder="30-12345678-9", 
                              key="cuit_single")
    
    # Opción para elegir entre campos activos o históricos
    tipo_busqueda = st.radio(
        "¿Qué campos querés buscar?",
        ["Solo campos activos", "Todos los campos (incluye históricos)"],
        key="tipo_busqueda_single",
        horizontal=True
    )
    
    if st.button("🔍 Buscar Campos", key="btn_buscar"):
        if cuit_input:
            try:
                cuit_normalizado = normalizar_cuit(cuit_input)
                
                with st.spinner('Buscando información...'):
                    campos = obtener_datos_por_cuit(cuit_normalizado)
                    
                    if not campos:
                        st.error("No se encontraron campos para este CUIT")
                        st.stop()
                    
                    # Guardar datos en session state para la pestaña de gráficos
                    st.session_state['ultimo_cuit'] = cuit_normalizado
                    st.session_state['ultimos_campos'] = campos
                    
                    # Filtrar según la opción seleccionada
                    if tipo_busqueda == "Solo campos activos":
                        campos_a_procesar = [c for c in campos if c.get('fecha_baja') is None]
                        if not campos_a_procesar:
                            st.warning("No hay campos activos para este CUIT")
                            st.stop()
                    else:
                        campos_a_procesar = campos
                    
                    # Procesar polígonos
                    poligonos = []
                    poligonos_sin_coords = []
                    
                    for campo in campos_a_procesar:
                        renspa = campo['renspa']
                        fecha_baja = campo.get('fecha_baja', None)
                        
                        # Primero intentar con los datos que ya tenemos
                        if 'poligono' in campo and campo['poligono']:
                            coords = extraer_coordenadas(campo['poligono'])
                            if coords:
                                poligonos.append({
                                    'coords': coords,
                                    'titular': campo.get('titular', ''),
                                    'localidad': campo.get('localidad', ''),
                                    'superficie': campo.get('superficie', 0),
                                    'cuit': cuit_normalizado,
                                    'fecha_baja': fecha_baja,
                                    'activo': fecha_baja is None
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
                                        'cuit': cuit_normalizado,
                                        'fecha_baja': fecha_baja,
                                        'activo': fecha_baja is None
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
                        campos_activos = [p for p in poligonos if p.get('activo', True)]
                        campos_inactivos = [p for p in poligonos if not p.get('activo', True)]
                        
                        st.success(f"✅ Se encontraron {len(poligonos)} campos con ubicación ({len(campos_activos)} activos, {len(campos_inactivos)} históricos)")
                        
                        # Mostrar estadísticas
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total de campos", len(poligonos))
                        with col2:
                            superficie_total = sum(p.get('superficie', 0) for p in poligonos)
                            st.metric("Superficie total", f"{superficie_total:,.1f} ha")
                        with col3:
                            superficie_activa = sum(p.get('superficie', 0) for p in campos_activos)
                            st.metric("Hectáreas activas", f"{superficie_activa:,.1f} ha")
                        with col4:
                            superficie_historica = sum(p.get('superficie', 0) for p in campos_inactivos)
                            st.metric("Hectáreas históricas", f"{superficie_historica:,.1f} ha")
                        
                        if poligonos_sin_coords:
                            st.info(f"ℹ️ {len(poligonos_sin_coords)} campos sin coordenadas disponibles")
                        
                        # Mostrar mapa si está disponible
                        if folium_disponible:
                            st.subheader("📍 Visualización de polígonos")
                            mapa = crear_mapa_mobile(poligonos)
                            if mapa:
                                folium_static(mapa, width=None, height=600)
                        else:
                            st.warning("Para visualizar mapas, instala folium y streamlit-folium")
                        
                        # Botones de descarga
                        st.subheader("📥 Descargar resultados")
                        col1, col2, col3 = st.columns(3)
                        
                        # Crear KML
                        kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>Campos del productor</name>
  <Style id="activePoly">
    <LineStyle>
      <color>ff0000ff</color>
      <width>3</width>
    </LineStyle>
    <PolyStyle>
      <color>7f0000ff</color>
    </PolyStyle>
  </Style>
  <Style id="historicPoly">
    <LineStyle>
      <color>ff0000ff</color>
      <width>2</width>
    </LineStyle>
    <PolyStyle>
      <color>3f0000ff</color>
    </PolyStyle>
  </Style>
"""
                        
                        for pol in poligonos:
                            style_id = "activePoly" if pol.get('activo', True) else "historicPoly"
                            estado = "Activo" if pol.get('activo', True) else "Histórico"
                            kml_content += f"""
  <Placemark>
    <name>{pol['titular']} ({estado})</name>
    <description>Localidad: {pol['localidad']} - Superficie: {pol['superficie']:.1f} ha - Estado: {estado}</description>
    <styleUrl>#{style_id}</styleUrl>
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
                        
                        # Crear GeoJSON
                        geojson_data = {
                            "type": "FeatureCollection",
                            "features": []
                        }
                        
                        for pol in poligonos:
                            feature = {
                                "type": "Feature",
                                "properties": {
                                    "titular": pol['titular'],
                                    "localidad": pol['localidad'],
                                    "superficie": pol['superficie'],
                                    "cuit": cuit_normalizado,
                                    "estado": "Activo" if pol.get('activo', True) else "Inactivo",
                                    "fecha_baja": pol.get('fecha_baja', None)
                                },
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [pol['coords']]
                                }
                            }
                            geojson_data["features"].append(feature)
                        
                        geojson_str = json.dumps(geojson_data, indent=2)
                        
                        # Crear CSV con información
                        df_export = pd.DataFrame([{
                            'Titular': p['titular'],
                            'Localidad': p['localidad'],
                            'Superficie (ha)': p['superficie'],
                            'Estado': 'Activo' if p.get('activo', True) else 'Inactivo',
                            'Fecha de baja': p.get('fecha_baja', 'N/A'),
                            'CUIT': p['cuit']
                        } for p in poligonos])
                        csv_data = df_export.to_csv(index=False).encode('utf-8')
                        
                        with col1:
                            st.download_button(
                                label="Descargar KMZ",
                                data=kmz_buffer,
                                file_name=f"campos_{cuit_normalizado.replace('-', '')}.kmz",
                                mime="application/vnd.google-earth.kmz",
                            )
                        
                        with col2:
                            st.download_button(
                                label="Descargar GeoJSON",
                                data=geojson_str,
                                file_name=f"campos_{cuit_normalizado.replace('-', '')}.geojson",
                                mime="application/json",
                            )
                        
                        with col3:
                            st.download_button(
                                label="Descargar CSV",
                                data=csv_data,
                                file_name=f"campos_{cuit_normalizado.replace('-', '')}.csv",
                                mime="text/csv",
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
    
    # Opción para elegir entre campos activos o históricos
    tipo_busqueda_multi = st.radio(
        "¿Qué campos querés buscar?",
        ["Solo campos activos", "Todos los campos (incluye históricos)"],
        key="tipo_busqueda_multi",
        horizontal=True
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
                            
                            # Filtrar según selección
                            if tipo_busqueda_multi == "Solo campos activos":
                                campos_a_procesar = [c for c in campos if c.get('fecha_baja') is None]
                            else:
                                campos_a_procesar = campos
                            
                            for campo in campos_a_procesar:
                                fecha_baja = campo.get('fecha_baja', None)
                                # Intentar extraer polígono de los datos básicos
                                if 'poligono' in campo and campo['poligono']:
                                    coords = extraer_coordenadas(campo['poligono'])
                                    if coords:
                                        todos_poligonos.append({
                                            'coords': coords,
                                            'titular': campo.get('titular', ''),
                                            'localidad': campo.get('localidad', ''),
                                            'superficie': campo.get('superficie', 0),
                                            'cuit': cuit_normalizado,
                                            'fecha_baja': fecha_baja,
                                            'activo': fecha_baja is None
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
                                                'cuit': cuit_normalizado,
                                                'fecha_baja': fecha_baja,
                                                'activo': fecha_baja is None
                                            })
                                
                                time.sleep(TIEMPO_ESPERA)
                            
                            cuits_procesados += 1
                            progress_bar.progress((i + 1) / len(cuit_list))
                            
                        except Exception as e:
                            cuits_con_error.append(cuit)
                            continue
                    
                    # Mostrar resumen
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("CUITs procesados", cuits_procesados)
                    with col2:
                        st.metric("Campos encontrados", len(todos_poligonos))
                    with col3:
                        superficie_total = sum(p.get('superficie', 0) for p in todos_poligonos)
                        st.metric("Superficie total", f"{superficie_total:,.1f} ha")
                    with col4:
                        campos_activos = [p for p in todos_poligonos if p.get('activo', True)]
                        st.metric("Campos activos", len(campos_activos))
                    
                    if todos_poligonos:
                        # Mostrar mapa si está disponible
                        if folium_disponible:
                            st.subheader("📍 Visualización de polígonos")
                            mapa = crear_mapa_mobile(todos_poligonos, cuit_colors=cuit_colors)
                            if mapa:
                                folium_static(mapa, width=None, height=600)
                        else:
                            st.warning("Para visualizar mapas, instala folium y streamlit-folium")
                        
                        # Mostrar estadísticas detalladas por CUIT
                        st.subheader("📊 Estadísticas por productor")
                        
                        # Agrupar datos por CUIT
                        cuits_unicos = list(set(p['cuit'] for p in todos_poligonos))
                        
                        for cuit in cuits_unicos:
                            campos_cuit = [p for p in todos_poligonos if p['cuit'] == cuit]
                            campos_activos_cuit = [p for p in campos_cuit if p.get('activo', True)]
                            campos_historicos_cuit = [p for p in campos_cuit if not p.get('activo', True)]
                            superficie_total_cuit = sum(p.get('superficie', 0) for p in campos_cuit)
                            superficie_activa_cuit = sum(p.get('superficie', 0) for p in campos_activos_cuit)
                            superficie_historica_cuit = sum(p.get('superficie', 0) for p in campos_historicos_cuit)
                            
                            # Obtener nombre del titular (usar el primero disponible)
                            titular = campos_cuit[0].get('titular', 'Sin información') if campos_cuit else 'Sin información'
                            
                            with st.expander(f"📊 {titular} - CUIT: {cuit}"):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total campos", len(campos_cuit))
                                    st.metric("Superficie total", f"{superficie_total_cuit:,.1f} ha")
                                with col2:
                                    st.metric("Campos activos", len(campos_activos_cuit))
                                    st.metric("Hectáreas activas", f"{superficie_activa_cuit:,.1f} ha")
                                with col3:
                                    st.metric("Campos históricos", len(campos_historicos_cuit))
                                    st.metric("Hectáreas históricas", f"{superficie_historica_cuit:,.1f} ha")
                                
                                # Detalles de campos
                                if campos_activos_cuit:
                                    st.write("**Campos Activos:**")
                                    for campo in campos_activos_cuit:
                                        st.write(f"• {campo.get('localidad', 'Sin localidad')} - {campo.get('superficie', 0):.1f} ha")
                                
                                if campos_historicos_cuit:
                                    st.write("**Campos Históricos:**")
                                    for campo in campos_historicos_cuit:
                                        fecha_baja = campo.get('fecha_baja', 'No disponible')
                                        st.write(f"• {campo.get('localidad', 'Sin localidad')} - {campo.get('superficie', 0):.1f} ha (hasta {fecha_baja})")
                    else:
                        st.warning("No se encontraron campos para los CUITs ingresados")
        else:
            st.warning("Por favor, ingresá al menos un CUIT")

with tab3:
    st.subheader("📊 Análisis temporal de hectáreas")
    
    # Verificar si hay datos en session state
    if 'ultimo_cuit' in st.session_state and 'ultimos_campos' in st.session_state:
        cuit_analisis = st.session_state['ultimo_cuit']
        campos_analisis = st.session_state['ultimos_campos']
        
        if campos_analisis:
            # Obtener razón social
            razon_social = campos_analisis[0].get('titular', 'Sin información')
            
            st.write(f"**Productor:** {razon_social}")
            st.write(f"**CUIT:** {cuit_analisis}")
            
            # Analizar evolución temporal
            df_temporal = analizar_hectareas_tiempo(campos_analisis)
            
            if df_temporal is not None and not df_temporal.empty:
                # Crear gráfico interactivo con Plotly
                fig = go.Figure()
                
                # Añadir línea de evolución
                fig.add_trace(go.Scatter(
                    x=df_temporal['Fecha'],
                    y=df_temporal['Hectáreas'],
                    mode='lines+markers',
                    name='Hectáreas activas',
                    line=dict(color='#00D2BE', width=3),
                    marker=dict(size=8, color='#00D2BE'),
                    fill='tozeroy',
                    fillcolor='rgba(0, 210, 190, 0.2)'
                ))
                
                # Configurar layout
                fig.update_layout(
                    title={
                        'text': f'Evolución de hectáreas activas - {razon_social}',
                        'x': 0.5,
                        'xanchor': 'center',
                        'font': {'size': 20, 'color': '#E0E0E0'}
                    },
                    xaxis_title='Fecha',
                    yaxis_title='Hectáreas',
                    hovermode='x unified',
                    plot_bgcolor='#1a1a1a',
                    paper_bgcolor='#0a0a0a',
                    font=dict(color='#E0E0E0'),
                    xaxis=dict(
                        gridcolor='#333333',
                        showgrid=True,
                        zeroline=False
                    ),
                    yaxis=dict(
                        gridcolor='#333333',
                        showgrid=True,
                        zeroline=True,
                        zerolinecolor='#666666'
                    ),
                    margin=dict(l=50, r=50, t=80, b=50)
                )
                
                # Mostrar gráfico
                st.plotly_chart(fig, use_container_width=True)
                
                # Mostrar estadísticas adicionales
                col1, col2, col3 = st.columns(3)
                with col1:
                    max_hectareas = df_temporal['Hectáreas'].max()
                    st.metric("Máximo histórico", f"{max_hectareas:,.1f} ha")
                with col2:
                    hectareas_actuales = df_temporal['Hectáreas'].iloc[-1] if not df_temporal.empty else 0
                    st.metric("Hectáreas actuales", f"{hectareas_actuales:,.1f} ha")
                with col3:
                    diferencia = hectareas_actuales - max_hectareas
                    st.metric("Diferencia vs máximo", f"{diferencia:,.1f} ha")
                
                # Tabla con eventos
                st.subheader("📅 Historial de cambios")
                
                eventos_df = []
                for campo in campos_analisis:
                    if campo.get('fecha_alta'):
                        eventos_df.append({
                            'Fecha': campo.get('fecha_alta', '').split('T')[0],
                            'Evento': 'Alta',
                            'Localidad': campo.get('localidad', 'Sin información'),
                            'Superficie (ha)': campo.get('superficie', 0)
                        })
                    
                    if campo.get('fecha_baja'):
                        eventos_df.append({
                            'Fecha': campo.get('fecha_baja', '').split('T')[0],
                            'Evento': 'Baja',
                            'Localidad': campo.get('localidad', 'Sin información'),
                            'Superficie (ha)': campo.get('superficie', 0)
                        })
                
                if eventos_df:
                    df_eventos = pd.DataFrame(eventos_df)
                    df_eventos = df_eventos.sort_values('Fecha', ascending=False)
                    st.dataframe(df_eventos, use_container_width=True, hide_index=True)
                
            else:
                st.warning("No hay suficientes datos temporales para generar el gráfico")
        else:
            st.info("No hay datos disponibles para analizar")
    else:
        st.info("Primero realizá una búsqueda por CUIT en la pestaña '🔍 Buscar por CUIT' para ver el análisis temporal")
        
        # Opción para ingresar CUIT manualmente
        st.write("---")
        cuit_grafico = st.text_input("O ingresá un CUIT para analizar:", 
                                    placeholder="30-12345678-9", 
                                    key="cuit_grafico")
        
        if st.button("📊 Generar Gráfico", key="btn_grafico"):
            if cuit_grafico:
                try:
                    cuit_normalizado = normalizar_cuit(cuit_grafico)
                    
                    with st.spinner('Obteniendo datos históricos...'):
                        campos = obtener_datos_por_cuit(cuit_normalizado)
                        
                        if campos:
                            st.session_state['ultimo_cuit'] = cuit_normalizado
                            st.session_state['ultimos_campos'] = campos
                            st.rerun()
                        else:
                            st.error("No se encontraron campos para este CUIT")
                except ValueError:
                    st.error("CUIT inválido. Verificá el formato.")
            else:
                st.warning("Por favor, ingresá un CUIT")
