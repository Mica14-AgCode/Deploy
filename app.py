                    else:
                        st.warning("No se encontraron campos para los CUITs ingresados")
        else:
            st.warning("Por favor, ingresá al menos un CUIT")

with tab3:
    st.write("Buscá campos por ciudad")
    
    # Lista de ciudades argentinas comunes (puedes expandir esta lista)
    ciudades_argentina = [
        "Buenos Aires", "Córdoba", "Rosario", "Mendoza", "La Plata", "San Miguel de Tucumán",
        "Mar del Plata", "Salta", "Santa Fe", "San Juan", "Resistencia", "Neuquén",
        "Santiago del Estero", "Corrientes", "Posadas", "San Salvador de Jujuy",
        "Bahía Blanca", "Paraná", "Formosa", "San Luis", "La Rioja", "Catamarca",
        "Río Cuarto", "Concordia", "Comodoro Rivadavia", "San Rafael", "Tandil",
        "Villa María", "San Nicolás", "Trelew", "Santa Rosa", "Venado Tuerto",
        "Zárate", "Pergamino", "Rafaela", "Olavarría", "Junín", "Necochea",
        "Río Gallegos", "Viedma", "Villa Mercedes", "Gualeguaychú", "Reconquista",
        "Villa Carlos Paz", "Cipolletti", "Campana", "Luján", "Goya", "Oberá",
        "Concepción del Uruguay", "La Banda", "Tartagal", "San Ramón de la Nueva Orán",
        "Mercedes", "Chivilcoy", "Azul", "Punta Alta", "San Francisco", "General Roca",
        "Puerto Madryn", "Presidencia Roque Sáenz Peña", "Balcarce", "Bell Ville",
        "Termas de Río Hondo", "Río Tercero", "Villas", "Eldorado", "Libertador General San Martín",
        "Banda del Río Salí", "Casilda", "Cañada de Gómez", "Esperanza", "Puerto Iguazú",
        "Esquel", "Villa Regina", "Caleta Olivia", "Avellaneda", "Quilmes", "Lanús",
        "Lomas de Zamora", "Almirante Brown", "La Matanza", "Morón", "Tres de Febrero",
        "San Isidro", "Vicente López", "San Martín", "Tigre", "Moreno", "Merlo",
        "Esteban Echeverría", "Pilar", "Escobar", "Florencio Varela", "San Fernando",
        "Ezeiza", "Ituzaingó", "Hurlingham", "Berazategui", "José C. Paz", "Malvinas Argentinas"
    ]
    
    # Input con autocompletado personalizado
    ciudad_input = st.text_input(
        "Empezá a escribir el nombre de la ciudad:",
        key="ciudad_search",
        placeholder="Ej: Boli..."
    )
    
    # Filtrar ciudades mientras se escribe
    if ciudad_input:
        # Filtrar ciudades que coincidan (case insensitive)
        ciudades_filtradas = [c for c in ciudades_argentina 
                             if c.lower().startswith(ciudad_input.lower())]
        
        # Mostrar hasta 5 sugerencias
        if ciudades_filtradas and len(ciudad_input) > 1:
            st.write("**Sugerencias:**")
            ciudad_seleccionada = None
            
            # Crear botones para cada sugerencia
            cols = st.columns(min(len(ciudades_filtradas[:5]), 3))
            for idx, ciudad in enumerate(ciudades_filtradas[:5]):
                with cols[idx % 3]:
                    if st.button(f"📍 {ciudad}", key=f"ciudad_{ciudad}"):
                        ciudad_seleccionada = ciudad
            
            # Si se seleccionó una ciudad, buscar
            if ciudad_seleccionada:
                st.session_state.ciudad_search = ciudad_seleccion                        # Mostrar mapa nativo de Streamlit
                        st.subheader("📍 Ubicación de los campos")
                        if puntos_mapa:
                            df_mapa = pd.DataFrame(puntos_mapa)
                            # Asegurar que las columnas tengan los nombres correctos
                            df_mapa = df_mapa.rename(columns={'lat': 'latitude', 'lon': 'longitudeimport streamlit as st
import pandas as pd
import numpy as np
import time
import json
import re
import requests
import zipfile
from io import BytesIO
import random

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

# Función para obtener el centro de un polígono
def obtener_centro_poligono(coords):
    """Obtiene el centro de un polígono"""
    if not coords:
        return None
    
    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]
    return [sum(lats) / len(lats), sum(lons) / len(lons)]

# Función para mostrar campos en tarjetas
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
    
    centro = obtener_centro_poligono(coords)
    if centro:
        return f"https://www.google.com/maps/@{centro[0]},{centro[1]},15z"
    return None

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
                    puntos_mapa = []
                    
                    for campo in campos_activos:
                        renspa = campo['renspa']
                        
                        # Primero intentar con los datos que ya tenemos
                        if 'poligono' in campo and campo['poligono']:
                            coords = extraer_coordenadas(campo['poligono'])
                            if coords:
                                centro = obtener_centro_poligono(coords)
                                if centro:
                                    poligonos.append({
                                        'coords': coords,
                                        'titular': campo.get('titular', ''),
                                        'localidad': campo.get('localidad', ''),
                                        'superficie': campo.get('superficie', 0),
                                        'cuit': cuit_normalizado,
                                        'centro': centro
                                    })
                                    puntos_mapa.append({
                                        'lat': centro[0],
                                        'lon': centro[1]
                                    })
                                continue
                        
                        # Si no tenemos polígono, consultar detalle
                        resultado_detalle = consultar_campo_detalle(renspa)
                        
                        if resultado_detalle and 'items' in resultado_detalle and resultado_detalle['items']:
                            item_detalle = resultado_detalle['items'][0]
                            if 'poligono' in item_detalle and item_detalle['poligono']:
                                coords = extraer_coordenadas(item_detalle['poligono'])
                                if coords:
                                    centro = obtener_centro_poligono(coords)
                                    if centro:
                                        poligonos.append({
                                            'coords': coords,
                                            'titular': campo.get('titular', ''),
                                            'localidad': campo.get('localidad', ''),
                                            'superficie': item_detalle.get('superficie', 0),
                                            'cuit': cuit_normalizado,
                                            'centro': centro
                                        })
                                        puntos_mapa.append({
                                            'lat': centro[0],
                                            'lon': centro[1]
                                        })
                        
                        time.sleep(TIEMPO_ESPERA)
                    
                    # Mostrar resultados
                    if poligonos:
                        st.success(f"✅ Se encontraron {len(poligonos)} campos activos con ubicación")
                        
                        # Mostrar mapa nativo de Streamlit
                        st.subheader("📍 Ubicación de los campos")
                        if puntos_mapa:
                            df_mapa = pd.DataFrame(puntos_mapa)
                            st.map(df_mapa, zoom=8, use_container_width=True)
                        
                        # Mostrar información de campos
                        st.subheader("📋 Detalle de los campos")
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            for i, campo in enumerate(poligonos):
                                with st.expander(f"📍 {campo['titular'] or f'Campo {i+1}'} - {campo['superficie']:.1f} ha"):
                                    st.write(f"**Localidad:** {campo['localidad']}")
                                    st.write(f"**CUIT:** {campo['cuit']}")
                                    link = generar_link_google_maps(campo['coords'])
                                    if link:
                                        st.markdown(f"[🗺️ Ver en Google Maps]({link})")
                        
                        with col2:
                            # Resumen estadístico
                            st.metric("Total de campos", len(poligonos))
                            superficie_total = sum(c.get('superficie', 0) for c in poligonos)
                            st.metric("Superficie total", f"{superficie_total:.1f} ha")
                        
                        # Botón de descarga KML
                        st.subheader("📥 Descargar datos")
                        
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
                            label="📥 Descargar archivo KML",
                            data=kmz_buffer,
                            file_name=f"campos_{cuit_normalizado.replace('-', '')}.kmz",
                            mime="application/vnd.google-earth.kmz",
                            help="Podés abrir este archivo en Google Earth para ver los polígonos completos"
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
                todos_poligonos = []
                todos_puntos_mapa = []
                cuits_procesados = 0
                cuits_con_error = []
                
                with st.spinner('Procesando...'):
                    progress_bar = st.progress(0)
                    
                    for i, cuit in enumerate(cuit_list):
                        try:
                            cuit_normalizado = normalizar_cuit(cuit)
                            
                            campos = obtener_datos_por_cuit(cuit_normalizado)
                            campos_activos = [c for c in campos if c.get('fecha_baja') is None]
                            
                            for campo in campos_activos:
                                # Intentar extraer polígono de los datos básicos
                                if 'poligono' in campo and campo['poligono']:
                                    coords = extraer_coordenadas(campo['poligono'])
                                    if coords:
                                        centro = obtener_centro_poligono(coords)
                                        if centro:
                                            todos_poligonos.append({
                                                'coords': coords,
                                                'titular': campo.get('titular', ''),
                                                'localidad': campo.get('localidad', ''),
                                                'superficie': campo.get('superficie', 0),
                                                'cuit': cuit_normalizado,
                                                'centro': centro
                                            })
                                            todos_puntos_mapa.append({
                                                'lat': centro[0],
                                                'lon': centro[1]
                                            })
                                        continue
                                
                                # Si no hay polígono, consultar detalle
                                resultado_detalle = consultar_campo_detalle(campo['renspa'])
                                
                                if resultado_detalle and 'items' in resultado_detalle and resultado_detalle['items']:
                                    item_detalle = resultado_detalle['items'][0]
                                    if 'poligono' in item_detalle and item_detalle['poligono']:
                                        coords = extraer_coordenadas(item_detalle['poligono'])
                                        if coords:
                                            centro = obtener_centro_poligono(coords)
                                            if centro:
                                                todos_poligonos.append({
                                                    'coords': coords,
                                                    'titular': campo.get('titular', ''),
                                                    'localidad': campo.get('localidad', ''),
                                                    'superficie': item_detalle.get('superficie', 0),
                                                    'cuit': cuit_normalizado,
                                                    'centro': centro
                                                })
                                                todos_puntos_mapa.append({
                                                    'lat': centro[0],
                                                    'lon': centro[1]
                                                })
                                
                                time.sleep(TIEMPO_ESPERA)
                            
                            cuits_procesados += 1
                            progress_bar.progress((i + 1) / len(cuit_list))
                            
                        except Exception as e:
                            cuits_con_error.append(cuit)
                            continue
                    
                    # Mostrar resumen
                    st.subheader("📊 Resumen del procesamiento")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("CUITs procesados", cuits_procesados)
                    with col2:
                        st.metric("Campos encontrados", len(todos_poligonos))
                    with col3:
                        superficie_total = sum(c.get('superficie', 0) for c in todos_poligonos)
                        st.metric("Superficie total", f"{superficie_total:.1f} ha")
                    
                    if todos_poligonos:
                        # Mostrar mapa con todos los puntos
                        st.subheader("📍 Ubicación de todos los campos")
                        if todos_puntos_mapa:
                            df_mapa = pd.DataFrame(todos_puntos_mapa)
                            st.map(df_mapa, zoom=6, use_container_width=True)
                        
                        # Agrupar por CUIT
                        st.subheader("📋 Campos por productor")
                        
                        cuits_unicos = list(set(c['cuit'] for c in todos_poligonos))
                        for cuit in cuits_unicos:
                            campos_cuit = [c for c in todos_poligonos if c['cuit'] == cuit]
                            superficie_cuit = sum(c.get('superficie', 0) for c in campos_cuit)
                            
                            with st.expander(f"CUIT: {cuit} - {len(campos_cuit)} campos - {superficie_cuit:.1f} ha total"):
                                for campo in campos_cuit:
                                    st.write(f"**📍 {campo['titular']}**")
                                    st.write(f"Localidad: {campo['localidad']} | Superficie: {campo['superficie']:.1f} ha")
                                    link = generar_link_google_maps(campo['coords'])
                                    if link:
                                        st.markdown(f"[Ver en Google Maps]({link})")
                                    st.divider()
                        
                        # Descargar KML con todos los campos
                        st.subheader("📥 Descargar todos los campos")
                        
                        kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>Campos múltiples productores</name>
"""
                        
                        # Colores para diferentes CUITs
                        colores_kml = ['ff0000ff', 'ffff0000', 'ff00ff00', 'ffffff00', 'ffff00ff', 'ff00ffff']
                        cuit_color_map = {cuit: colores_kml[i % len(colores_kml)] for i, cuit in enumerate(cuits_unicos)}
                        
                        # Crear estilos
                        for cuit, color in cuit_color_map.items():
                            cuit_clean = cuit.replace('-', '_')
                            kml_content += f"""
  <Style id="style_{cuit_clean}">
    <LineStyle>
      <color>{color}</color>
      <width>3</width>
    </LineStyle>
    <PolyStyle>
      <color>7f{color[2:]}</color>
    </PolyStyle>
  </Style>
"""
                        
                        # Añadir placemarks
                        for campo in todos_poligonos:
                            cuit_clean = campo['cuit'].replace('-', '_')
                            kml_content += f"""
  <Placemark>
    <name>{campo['titular']}</name>
    <description>CUIT: {campo['cuit']} - Localidad: {campo['localidad']} - Superficie: {campo['superficie']:.1f} ha</description>
    <styleUrl>#style_{cuit_clean}</styleUrl>
    <Polygon>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>
"""
                            for coord in campo['coords']:
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
                            label="📥 Descargar archivo KML con todos los campos",
                            data=kmz_buffer,
                            file_name="campos_multiples.kmz",
                            mime="application/vnd.google-earth.kmz",
                            help="Podés abrir este archivo en Google Earth para ver todos los polígonos"
                        )
                    else:
                        st.warning("No se encontraron campos para los CUITs ingresados")
        else:
            st.warning("Por favor, ingresá al menos un CUIT")
