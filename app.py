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
import os
import sys
import subprocess

# Configuración de la página
st.set_page_config(
    page_title="Consulta RENSPA - SENASA",
    page_icon="🌱",
    layout="wide"
)

# Título principal
st.title("Consulta RENSPA desde SENASA")

# Detectar entorno Streamlit Cloud
is_cloud = os.environ.get('SUDO_USER') == 'adminuser' or 'STREAMLIT_RUNTIME' in os.environ

# Intentar instalar dependencias si es necesario
def instalar_dependencia(paquete, version=None):
    paquete_version = f"{paquete}=={version}" if version else paquete
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", paquete_version])
        return True
    except:
        return False

# Verificación de dependencias al inicio
with st.sidebar:
    st.sidebar.title("Diagnóstico del Sistema")
    st.sidebar.write(f"Python version: {sys.version}")
    st.sidebar.write(f"Ejecutando en Streamlit Cloud: {is_cloud}")
    
    # Intentar cargar folium
    folium_disponible = False
    try:
        import folium
        from folium.plugins import MeasureControl, MiniMap, MarkerCluster
        from streamlit_folium import folium_static
        st.sidebar.success(f"✅ Folium {folium.__version__} disponible")
        folium_disponible = True
    except ImportError as e:
        st.sidebar.error(f"❌ Folium no disponible: {str(e)}")
        st.sidebar.info("Para instalar Folium: pip install folium==0.14.0 streamlit-folium==0.13.0")
        # Intentar instalar en tiempo de ejecución
        if st.sidebar.button("Intentar instalar Folium"):
            with st.spinner("Instalando Folium..."):
                if instalar_dependencia("folium", "0.14.0") and instalar_dependencia("streamlit-folium", "0.13.0"):
                    st.sidebar.success("✅ Folium instalado. Por favor, reinicia la aplicación.")
                    st.stop()
                else:
                    st.sidebar.error("❌ No se pudo instalar Folium")

    # Intentar cargar Earth Engine
    ee_disponible = False
    ee_inicializado = False
    try:
        import ee
        st.sidebar.success(f"✅ Earth Engine API disponible")
        
        # Ahora intentar importar geemap
        try:
            import geemap
            try:
                version = geemap.__version__
                st.sidebar.success(f"✅ Geemap {version} disponible")
            except:
                st.sidebar.success(f"✅ Geemap disponible (versión desconocida)")
                
            ee_disponible = True
            
            # Inicialización de Earth Engine solo si tenemos los módulos
            if ee_disponible:
                try:
                    # Si estamos en Streamlit Cloud y hay credenciales, usarlas
                    if is_cloud and hasattr(st, 'secrets'):
                        if 'EARTHENGINE_TOKEN' in st.secrets:
                            st.sidebar.info("Usando EARTHENGINE_TOKEN para autenticación")
                            geemap.ee_initialize()
                            ee_inicializado = True
                            st.sidebar.success("✅ Earth Engine inicializado con token")
                        elif 'gcp_service_account' in st.secrets:
                            st.sidebar.info("Usando cuenta de servicio para autenticación")
                            credentials_dict = st.secrets["gcp_service_account"]
                            if 'private_key' in credentials_dict:
                                credentials_dict['private_key'] = credentials_dict['private_key'].replace('\\n', '\n')
                            
                            credentials = ee.ServiceAccountCredentials(
                                email=credentials_dict["client_email"],
                                key_data=json.dumps(credentials_dict)
                            )
                            ee.Initialize(credentials)
                            ee_inicializado = True
                            st.sidebar.success("✅ Earth Engine inicializado con cuenta de servicio")
                        else:
                            st.sidebar.warning("⚠️ No se encontraron credenciales para Earth Engine")
                    else:
                        # Inicialización en entorno local
                        try:
                            ee.Initialize()
                            ee_inicializado = True
                            st.sidebar.success("✅ Earth Engine inicializado (local)")
                        except Exception as e:
                            st.sidebar.error(f"❌ No se pudo inicializar Earth Engine: {str(e)}")
                except Exception as init_error:
                    st.sidebar.error(f"❌ Error al inicializar Earth Engine: {str(init_error)}")
        
        except ImportError as geemap_error:
            st.sidebar.error(f"❌ Geemap no disponible: {str(geemap_error)}")
            
    except ImportError as ee_error:
        st.sidebar.error(f"❌ Earth Engine API no disponible: {str(ee_error)}")
        st.sidebar.info("Para instalar Earth Engine: pip install earthengine-api==0.1.348 geemap==0.20.6")
        # Intentar instalar en tiempo de ejecución
        if st.sidebar.button("Intentar instalar Earth Engine"):
            with st.spinner("Instalando Earth Engine y Geemap..."):
                if instalar_dependencia("earthengine-api", "0.1.348") and instalar_dependencia("geemap", "0.20.6"):
                    st.sidebar.success("✅ Earth Engine y Geemap instalados. Por favor, reinicia la aplicación.")
                    st.stop()
                else:
                    st.sidebar.error("❌ No se pudo instalar Earth Engine")

# Modo de depuración avanzado
with st.sidebar:
    st.sidebar.markdown("---")
    debug_mode = st.sidebar.checkbox("Modo depuración avanzado", value=False)
    
    if debug_mode:
        st.sidebar.markdown("---")
        st.sidebar.write("**Información de diagnóstico avanzada:**")
        st.sidebar.write(f"- Earth Engine importado: {ee_disponible}")
        st.sidebar.write(f"- Earth Engine inicializado: {ee_inicializado}")
        
        # Detalles del entorno
        st.sidebar.write("**Variables de entorno:**")
        env_vars = dict(os.environ)
        # Filtrar solo las variables seguras/relevantes
        safe_vars = {k: v for k, v in env_vars.items() if 'key' not in k.lower() and 'token' not in k.lower() and 'secret' not in k.lower() and 'password' not in k.lower()}
        if st.sidebar.checkbox("Mostrar variables de entorno", value=False):
            st.sidebar.json(safe_vars)
        
        # Detalles de secrets (sin mostrar valores sensibles)
        if is_cloud and hasattr(st, 'secrets') and st.secrets:
            st.sidebar.write("**Configuración de Secrets:**")
            secret_keys = list(st.secrets.keys()) if hasattr(st, 'secrets') else []
            st.sidebar.write(f"Claves configuradas: {', '.join(secret_keys)}")

# Configuraciones globales
API_BASE_URL = "https://aps.senasa.gob.ar/restapiprod/servicios/renspa"
TIEMPO_ESPERA = 0.5  # Pausa entre peticiones para no sobrecargar la API

# Introducción
st.markdown(f"""
Esta herramienta permite:

1. Consultar todos los RENSPA asociados a un CUIT en la base de datos de SENASA
2. Visualizar los polígonos de los campos en un mapa interactivo
3. Descargar los datos en formato KMZ/GeoJSON para su uso en sistemas GIS
""")

# Si Earth Engine está disponible, añadir esa funcionalidad a la introducción
if ee_disponible and ee_inicializado:
    st.markdown("4. Analizar los cultivos históricos de los campos (usando Google Earth Engine)")

# Función para crear análisis de cultivos con Earth Engine
def crear_analisis_cultivos(poligonos):
    """
    Crea un análisis de cultivos históricos usando Google Earth Engine
    
    Args:
        poligonos: Lista de diccionarios con información de polígonos
    """
    if not ee_disponible:
        st.error("Google Earth Engine no está disponible. Instala las dependencias necesarias.")
        st.info("Ejecuta: pip install earthengine-api==0.1.348 geemap==0.20.6")
        return
    
    if not ee_inicializado:
        st.error("Google Earth Engine no está inicializado correctamente.")
        st.info("Verifica las credenciales o ejecuta: earthengine authenticate")
        return
    
    try:
        # Crear un mapa de Earth Engine
        m = geemap.Map()
        
        # Añadir control de capas
        m.add_layer_control()
        
        # Procesar cada polígono
        for i, pol in enumerate(poligonos):
            if 'coords' in pol:
                # Convertir coordenadas de [lon, lat] a [lat, lon] para EE
                ee_coords = [[coord[1], coord[0]] for coord in pol['coords']]
                
                # Crear polígono para Earth Engine
                polygon = ee.Geometry.Polygon([ee_coords])
                
                # Añadir polígono al mapa como capa vectorial
                m.add_layer(ee.Feature(polygon), {'color': 'red'}, f"Polígono {i+1}")
        
        # Añadir capa de cobertura de cultivos mundial
        dataset = ee.ImageCollection("MODIS/006/MCD12Q1")
        landcover = dataset.filter(ee.Filter.date('2019-01-01', '2023-12-31'))
        
        # Crear una visualización para los tipos de cultivos
        landcover_vis = {
            'bands': ['LC_Type1'],
            'min': 1,
            'max': 17,
            'palette': [
                '05450a', '086a10', '54a708', '78d203', '009900',
                'c6b044', 'dcd159', 'dade48', 'fbff13', 'b6ff05',
                '27ff87', 'c24f44', 'a5a5a5', 'ff6d4c', '69fff8',
                'f9ffa4', '1c0dff'
            ]
        }
        
        # Añadir capa de cobertura terrestre
        m.add_ee_layer(landcover.first(), landcover_vis, 'Cobertura Terrestre (2019)')
        
        # Mostrar el mapa
        st.subheader("Análisis de Cobertura Terrestre")
        m.to_streamlit(height=600)
        
        # Explicación de los colores
        st.info("""
        **Leyenda:**
        - Verde oscuro: Bosques
        - Verde claro: Arbustos y pastizales
        - Amarillo/Naranja: Cultivos y tierras agrícolas
        - Rojo: Urbano
        - Gris: Terreno estéril o escasamente vegetado
        - Azul: Agua
        """)
        
        # Añadir nota sobre la precisión
        st.warning("Nota: Este análisis se basa en datos satelitales de resolución moderada. Para análisis más detallados, considere consultar con un especialista en teledetección.")
        
    except Exception as e:
        st.error(f"Error al crear el análisis de cultivos: {str(e)}")
        st.info("Si el error persiste, contacte con soporte técnico.")

# Función para normalizar CUIT
def normalizar_cuit(cuit):
    """Normaliza un CUIT a formato XX-XXXXXXXX-X"""
    # Eliminar guiones si están presentes
    cuit_limpio = cuit.replace("-", "")
    
    # Validar longitud
    if len(cuit_limpio) != 11:
        raise ValueError(f"CUIT inválido: {cuit}. Debe tener 11 dígitos.")
    
    # Reformatear con guiones
    return f"{cuit_limpio[:2]}-{cuit_limpio[2:10]}-{cuit_limpio[10]}"

# Función para obtener RENSPA por CUIT
def obtener_renspa_por_cuit(cuit):
    """
    Obtiene todos los RENSPA asociados a un CUIT, manejando la paginación
    """
    try:
        # URL base para la consulta
        url_base = f"{API_BASE_URL}/consultaPorCuit"
        
        todos_renspa = []
        offset = 0
        limit = 10  # La API usa un límite de 10 por página
        has_more = True
        
        # Realizar consultas sucesivas hasta obtener todos los RENSPA
        while has_more:
            # Construir URL con offset para paginación
            url = f"{url_base}?cuit={cuit}&offset={offset}"
            
            try:
                # Realizar la consulta a la API
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                resultado = response.json()
                
                # Verificar si hay resultados
                if 'items' in resultado and resultado['items']:
                    # Agregar los RENSPA a la lista total
                    todos_renspa.extend(resultado['items'])
                    
                    # Verificar si hay más páginas
                    has_more = resultado.get('hasMore', False)
                    
                    # Actualizar offset para la siguiente página
                    offset += limit
                else:
                    has_more = False
            
            except Exception as e:
                st.error(f"Error consultando la API: {str(e)}")
                has_more = False
                
            # Pausa breve para no sobrecargar la API
            time.sleep(TIEMPO_ESPERA)
        
        return todos_renspa
    
    except Exception as e:
        st.error(f"Error al obtener RENSPA: {str(e)}")
        return []

# Función para normalizar RENSPA
def normalizar_renspa(renspa):
    """Normaliza un RENSPA al formato ##.###.#.#####/##"""
    # Eliminar espacios
    renspa_limpio = renspa.strip()
    
    # Ya tiene el formato correcto con puntos y barra
    if re.match(r'^\d{2}\.\d{3}\.\d\.\d{5}/\d{2}$', renspa_limpio):
        return renspa_limpio
    
    # Tiene el formato numérico sin puntos ni barra
    # Formato esperado: XXYYYZWWWWWDD (XX.YYY.Z.WWWWW/DD)
    if re.match(r'^\d{13}$', renspa_limpio):
        return f"{renspa_limpio[0:2]}.{renspa_limpio[2:5]}.{renspa_limpio[5:6]}.{renspa_limpio[6:11]}/{renspa_limpio[11:13]}"
    
    raise ValueError(f"Formato de RENSPA inválido: {renspa}")

# Función para consultar detalles de un RENSPA
def consultar_renspa_detalle(renspa):
    """
    Consulta los detalles de un RENSPA específico para obtener el polígono
    """
    try:
        url = f"{API_BASE_URL}/consultaPorNumero?numero={renspa}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        st.error(f"Error consultando {renspa}: {e}")
        return None

# Función para extraer coordenadas de un polígono
def extraer_coordenadas(poligono_str):
    """
    Extrae coordenadas de un string de polígono en el formato de SENASA
    """
    if not poligono_str or not isinstance(poligono_str, str):
        return None
    
    # Extraer pares de coordenadas
    coord_pattern = r'\(([-\d\.]+),([-\d\.]+)\)'
    coord_pairs = re.findall(coord_pattern, poligono_str)
    
    if not coord_pairs:
        return None
    
    # Convertir a formato [lon, lat] para GeoJSON
    coords_geojson = []
    for lat_str, lon_str in coord_pairs:
        try:
            lat = float(lat_str)
            lon = float(lon_str)
            coords_geojson.append([lon, lat])  # GeoJSON usa [lon, lat]
        except ValueError:
            continue
    
    # Verificar que hay al menos 3 puntos y que el polígono está cerrado
    if len(coords_geojson) >= 3:
        # Para polígonos válidos, asegurarse de que está cerrado
        if coords_geojson[0] != coords_geojson[-1]:
            coords_geojson.append(coords_geojson[0])  # Cerrar el polígono
        
        return coords_geojson
    
    return None

# Función para crear mapa con múltiples mejoras
def crear_mapa_mejorado(poligonos, center=None, cuit_colors=None):
    """
    Crea un mapa folium mejorado con los polígonos proporcionados
    
    Args:
        poligonos: Lista de diccionarios con los datos de polígonos
        center: Coordenadas del centro del mapa (opcional)
        cuit_colors: Diccionario de colores por CUIT (opcional)
        
    Returns:
        Objeto mapa de folium
    """
    if not folium_disponible:
        st.warning("Para visualizar mapas, instala folium y streamlit-folium con: pip install folium==0.14.0 streamlit-folium==0.13.0")
        return None
    
    # Determinar centro del mapa
    if center:
        # Usar centro proporcionado
        center_lat, center_lon = center
    elif poligonos:
        # Usar el primer polígono como referencia
        center_lat = poligonos[0]['coords'][0][1]  # Latitud está en la segunda posición
        center_lon = poligonos[0]['coords'][0][0]  # Longitud está en la primera posición
    else:
        # Centro predeterminado (Buenos Aires)
        center_lat = -34.603722
        center_lon = -58.381592
    
    # Crear mapa base
    m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
    
    # Añadir diferentes capas base con atribución para evitar errores
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                    name='Google Hybrid', 
                    attr='Google').add_to(m)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                    name='Google Satellite', 
                    attr='Google').add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    
    # Añadir herramienta de medición si está disponible
    try:
        MeasureControl(position='topright', 
                      primary_length_unit='kilometers', 
                      secondary_length_unit='miles', 
                      primary_area_unit='hectares').add_to(m)
    except:
        pass
    
    # Añadir mini mapa si está disponible
    try:
        MiniMap().add_to(m)
    except:
        pass
    
    # Crear grupos de capas para mejor organización
    fg_poligonos = folium.FeatureGroup(name="Polígonos RENSPA").add_to(m)
    
    # Añadir cada polígono al mapa
    for pol in poligonos:
        # Determinar color según CUIT si está disponible
        if cuit_colors and 'cuit' in pol and pol['cuit'] in cuit_colors:
            color = cuit_colors[pol['cuit']]
        else:
            color = 'green'
        
        # Formatear popup con información
        popup_text = f"""
        <b>RENSPA:</b> {pol['renspa']}<br>
        <b>Titular:</b> {pol.get('titular', 'No disponible')}<br>
        <b>Localidad:</b> {pol.get('localidad', 'No disponible')}<br>
        <b>Superficie:</b> {pol.get('superficie', 0)} ha
        """
        if 'cuit' in pol:
            popup_text += f"<br><b>CUIT:</b> {pol['cuit']}"
        
        # Añadir polígono al mapa
        folium.Polygon(
            locations=[[coord[1], coord[0]] for coord in pol['coords']],  # Invertir coordenadas para folium
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.3,
            tooltip=f"RENSPA: {pol['renspa']}",
            popup=popup_text
        ).add_to(fg_poligonos)
    
    # Añadir control de capas
    folium.LayerControl(position='topright').add_to(m)
    
    return m

# Función para mostrar estadísticas de RENSPA
def mostrar_estadisticas(df_renspa, poligonos=None):
    """
    Muestra estadísticas sobre los RENSPA procesados
    
    Args:
        df_renspa: DataFrame con los datos de RENSPA
        poligonos: Lista de diccionarios con los polígonos (opcional)
    """
    st.subheader("Estadísticas de RENSPA")
    
    if df_renspa.empty:
        st.warning("No hay datos para mostrar estadísticas.")
        return
    
    # Crear columnas para estadísticas básicas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Contar RENSPA activos e inactivos
        activos = df_renspa[df_renspa['fecha_baja'].isnull()].shape[0]
        inactivos = df_renspa[~df_renspa['fecha_baja'].isnull()].shape[0]
        st.metric("Total RENSPA", df_renspa.shape[0])
    
    with col2:
        st.metric("RENSPA activos", activos)
    
    with col3:
        st.metric("RENSPA inactivos", inactivos)
    
    # Si hay polígonos, mostrar estadísticas adicionales
    if poligonos:
        st.subheader("Estadísticas de Polígonos")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Polígonos encontrados", len(poligonos))
        
        with col2:
            # Calcular área total de los polígonos
            area_total = sum(pol.get('superficie', 0) for pol in poligonos)
            st.metric("Área total", f"{area_total:.2f} ha")
        
        with col3:
            # Promedio de área por polígono
            if poligonos:
                area_promedio = area_total / len(poligonos)
                st.metric("Área promedio", f"{area_promedio:.2f} ha")

# Crear tabs para las diferentes funcionalidades
tab1, tab2, tab3 = st.tabs(["Consulta por CUIT", "Consulta por Lista de RENSPA", "Consulta por Múltiples CUITs"])

with tab1:
    st.header("Consulta por CUIT")
    cuit_input = st.text_input("Ingrese el CUIT (formato: XX-XXXXXXXX-X o XXXXXXXXXXX):", 
                              value="30-65425756-2", key="cuit_single")

    # Opciones de procesamiento
    col1, col2 = st.columns(2)
    with col1:
        solo_activos = st.checkbox("Solo RENSPA activos", value=True)
    with col2:
        incluir_poligono = st.checkbox("Incluir información de polígonos", value=True)

    # Botón para procesar
    if st.button("Consultar RENSPA", key="btn_cuit"):
        try:
            # Normalizar CUIT
            cuit_normalizado = normalizar_cuit(cuit_input)
            
            # Mostrar un indicador de procesamiento
            with st.spinner('Consultando RENSPA desde SENASA...'):
                # Crear barras de progreso
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Paso 1: Obtener todos los RENSPA para el CUIT
                status_text.text("Obteniendo listado de RENSPA...")
                progress_bar.progress(20)
                
                todos_renspa = obtener_renspa_por_cuit(cuit_normalizado)
                
                if not todos_renspa:
                    st.error(f"No se encontraron RENSPA para el CUIT {cuit_normalizado}")
                    st.stop()
                
                # Crear DataFrame para mejor visualización y manipulación
                df_renspa = pd.DataFrame(todos_renspa)
                
                # Contar RENSPA activos e inactivos
                activos = df_renspa[df_renspa['fecha_baja'].isnull()].shape[0]
                inactivos = df_renspa[~df_renspa['fecha_baja'].isnull()].shape[0]
                
                st.success(f"Se encontraron {len(todos_renspa)} RENSPA en total ({activos} activos, {inactivos} inactivos)")
                
                # Filtrar según la opción seleccionada
                if solo_activos:
                    renspa_a_procesar = df_renspa[df_renspa['fecha_baja'].isnull()].to_dict('records')
                    st.info(f"Se procesarán {len(renspa_a_procesar)} RENSPA activos")
                else:
                    renspa_a_procesar = todos_renspa
                    st.info(f"Se procesarán todos los {len(renspa_a_procesar)} RENSPA")
                
                # Paso 2: Procesar los RENSPA para obtener los polígonos
                poligonos_gee = []
                if incluir_poligono:
                    status_text.text("Obteniendo información de polígonos...")
                    progress_bar.progress(40)
                    
                    # Listas para almacenar resultados
                    fallidos = []
                    renspa_sin_poligono = []
                    
                    # Procesar cada RENSPA
                    for i, item in enumerate(renspa_a_procesar):
                        renspa = item['renspa']
                        # Actualizar progreso
                        progress_percentage = 40 + (i * 40 // len(renspa_a_procesar))
                        progress_bar.progress(progress_percentage)
                        status_text.text(f"Procesando RENSPA: {renspa} ({i+1}/{len(renspa_a_procesar)})")
                        
                        # Verificar si ya tiene el polígono en la información básica
                        if 'poligono' in item and item['poligono']:
                            poligono_str = item['poligono']
                            superficie = item.get('superficie', 0)
                            
                            # Extraer coordenadas
                            coordenadas = extraer_coordenadas(poligono_str)
                            
                            if coordenadas:
                                # Crear objeto con datos del polígono
                                poligono_data = {
                                    'renspa': renspa,
                                    'coords': coordenadas,
                                    'superficie': superficie,
                                    'titular': item.get('titular', ''),
                                    'localidad': item.get('localidad', ''),
                                    'cuit': cuit_normalizado
                                }
                                poligonos_gee.append(poligono_data)
                                continue
                        
                        # Si no tenía polígono o no era válido, consultar más detalles
                        resultado = consultar_renspa_detalle(renspa)
                        
                        if resultado and 'items' in resultado and resultado['items'] and 'poligono' in resultado['items'][0]:
                            item_detalle = resultado['items'][0]
                            poligono_str = item_detalle.get('poligono')
                            superficie = item_detalle.get('superficie', 0)
                            
                            if poligono_str:
                                # Extraer coordenadas
                                coordenadas = extraer_coordenadas(poligono_str)
                                
                                if coordenadas:
                                    # Crear objeto con datos del polígono
                                    poligono_data = {
                                        'renspa': renspa,
                                        'coords': coordenadas,
                                        'superficie': superficie,
                                        'titular': item.get('titular', ''),
                                        'localidad': item.get('localidad', ''),
                                        'cuit': cuit_normalizado
                                    }
                                    poligonos_gee.append(poligono_data)
                                else:
                                    fallidos.append(renspa)
                            else:
                                renspa_sin_poligono.append(renspa)
                        else:
                            renspa_sin_poligono.append(renspa)
                        
                        # Pausa breve para no sobrecargar la API
                        time.sleep(TIEMPO_ESPERA)
                    
                    # Mostrar estadísticas de procesamiento
                    total_procesados = len(renspa_a_procesar)
                    total_exitosos = len(poligonos_gee)
                    total_fallidos = len(fallidos)
                    total_sin_poligono = len(renspa_sin_poligono)
                    
                    st.subheader("Estadísticas de procesamiento")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total procesados", total_procesados)
                    with col2:
                        st.metric("Con polígono", total_exitosos)
                    with col3:
                        st.metric("Sin polígono", total_sin_poligono + total_fallidos)
                
                # Mostrar los datos en formato de tabla
                status_text.text("Generando resultados...")
                progress_bar.progress(80)
                
                st.subheader("Listado de RENSPA")
                st.dataframe(df_renspa)
                
                # Panel de estadísticas
                if 'df_renspa' in locals() and not df_renspa.empty:
                    mostrar_estadisticas(df_renspa, poligonos_gee if incluir_poligono else None)
                
                # Si se procesaron polígonos, mostrarlos en el mapa
                if incluir_poligono and poligonos_gee and folium_disponible:
                    # Crear mapa para visualización
                    st.subheader("Visualización de polígonos")
                    
                    # Crear mapa mejorado
                    m = crear_mapa_mejorado(poligonos_gee)
                    
                    # Mostrar el mapa
                    folium_static(m, width=1000, height=600)
                    
                    # Si Earth Engine está disponible, mostrar botón para análisis de cultivos
                    if ee_disponible and ee_inicializado:
                        # Agregar botón para análisis de cultivos con Google Earth Engine
                        st.subheader("Análisis de Cultivos Históricos")
                        
                        # Mostrar información sobre el servicio
                        st.info("""
                        Puede analizar los cultivos históricos (2019-2024) utilizando los datos de Google Earth Engine.
                        Este análisis mostrará cómo ha cambiado el uso de la tierra en estos campos año a año.
                        """)
                        
                        # Crear botón de análisis
                        if st.button("Analizar Cultivos Históricos"):
                            crear_analisis_cultivos(poligonos_gee)
                    
                elif incluir_poligono and not folium_disponible:
                    st.warning("Para visualizar mapas, instala folium y streamlit-folium con: pip install folium==0.14.0 streamlit-folium==0.13.0")
                
                # Generar archivo KMZ para descarga
                if incluir_poligono and poligonos_gee:
                    status_text.text("Preparando archivos para descarga...")
                    progress_bar.progress(90)
                    
                    # Crear archivo KML
                    kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>RENSPA - CUIT {cuit_normalizado}</name>
  <description>Polígonos de RENSPA para el CUIT {cuit_normalizado}</description>
  <Style id="greenPoly">
    <LineStyle>
      <color>ff009900</color>
      <width>3</width>
    </LineStyle>
    <PolyStyle>
      <color>7f00ff00</color>
    </PolyStyle>
  </Style>
"""
                    
                    # Añadir cada polígono al KML
                    for pol in poligonos_gee:
                        kml_content += f"""
  <Placemark>
    <name>{pol['renspa']}</name>
    <description><![CDATA[
      <b>RENSPA:</b> {pol['renspa']}<br/>
      <b>Titular:</b> {pol['titular']}<br/>
      <b>Localidad:</b> {pol['localidad']}<br/>
      <b>Superficie:</b> {pol['superficie']} ha
    ]]></description>
    <styleUrl>#greenPoly</styleUrl>
    <Polygon>
      <extrude>1</extrude>
      <altitudeMode>clampToGround</altitudeMode>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>
"""
                        
                        # Añadir coordenadas
                        for coord in pol['coords']:
                            lon = coord[0]
                            lat = coord[1]
                            kml_content += f"{lon},{lat},0\n"
                        
                        kml_content += """
          </coordinates>
        </LinearRing>
      </outerBoundaryIs>
    </Polygon>
  </Placemark>
"""
                    
                    # Cerrar documento KML
                    kml_content += """
</Document>
</kml>
"""
                    
                    # Crear archivo KMZ (ZIP que contiene el KML)
                    kmz_buffer = BytesIO()
                    with zipfile.ZipFile(kmz_buffer, 'w', zipfile.ZIP_DEFLATED) as kmz:
                        kmz.writestr("doc.kml", kml_content)
                    
                    kmz_buffer.seek(0)
                    
                    # Crear también un GeoJSON
                    geojson_data = {
                        "type": "FeatureCollection",
                        "features": []
                    }
                    
                    for pol in poligonos_gee:
                        feature = {
                            "type": "Feature",
                            "properties": {
                                "renspa": pol['renspa'],
                                "titular": pol['titular'],
                                "localidad": pol['localidad'],
                                "superficie": pol['superficie'],
                                "cuit": cuit_normalizado
                            },
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [pol['coords']]
                            }
                        }
                        geojson_data["features"].append(feature)
                    
                    geojson_str = json.dumps(geojson_data, indent=2)
                    
                    # Preparar CSV con todos los datos
                    csv_data = df_renspa.to_csv(index=False).encode('utf-8')
                    
                    # Opciones de descarga
                    st.subheader("Descargar resultados")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.download_button(
                            label="Descargar KMZ",
                            data=kmz_buffer,
                            file_name=f"renspa_{cuit_normalizado.replace('-', '')}.kmz",
                            mime="application/vnd.google-earth.kmz",
                        )
                    
                    with col2:
                        st.download_button(
                            label="Descargar GeoJSON",
                            data=geojson_str,
                            file_name=f"renspa_{cuit_normalizado.replace('-', '')}.geojson",
                            mime="application/json",
                        )
                    
                    with col3:
                        st.download_button(
                            label="Descargar CSV",
                            data=csv_data,
                            file_name=f"renspa_{cuit_normalizado.replace('-', '')}.csv",
                            mime="text/csv",
                        )
                
                # Completar procesamiento
                status_text.text("Procesamiento completo!")
                progress_bar.progress(100)
        
        except Exception as e:
            st.error(f"Error durante el procesamiento: {str(e)}")

# Con los tabs 2 y 3 se pueden agregar las demás funcionalidades según necesites

# Información en la barra lateral
st.sidebar.markdown("---")

# Mostrar información sobre Google Earth Engine
st.sidebar.subheader("Google Earth Engine")

if ee_disponible and ee_inicializado:
    st.sidebar.success(f"Google Earth Engine está disponible y correctamente inicializado.")
    st.sidebar.info("""
    Esta herramienta permite analizar los cultivos históricos (2019-2023) 
    en los campos utilizando datos satelitales de alta resolución.
    
    Para utilizar esta función, seleccione los polígonos de interés y
    luego haga clic en "Analizar Cultivos Históricos".
    """)
elif ee_disponible and not ee_inicializado:
    st.sidebar.warning("Google Earth Engine está disponible pero no inicializado.")
    st.sidebar.info("""
    Earth Engine requiere autenticación para acceder a los datos satelitales.
    
    Para habilitarlo:
    1. Instale las dependencias: pip install earthengine-api==0.1.348 geemap==0.20.6
    2. Configure credenciales en Streamlit Cloud
    """)
else:
    st.sidebar.warning("Google Earth Engine no está disponible")
    st.sidebar.info(
        "Para habilitar el análisis de cultivos históricos, instala las siguientes dependencias:\n"
        "```\npip install earthengine-api==0.1.348 geemap==0.20.6\n```"
    )

# Información en el pie de página
st.sidebar.markdown("---")
st.sidebar.info("Desarrollado para análisis agrícola en Argentina")
