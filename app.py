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
    page_title="Consulta RENSPA - SENASA",
    page_icon="🌱",
    layout="wide"
)

# Configuraciones globales
API_BASE_URL = "https://aps.senasa.gob.ar/restapiprod/servicios/renspa"
TIEMPO_ESPERA = 0.5  # Pausa entre peticiones para no sobrecargar la API

# Título principal
st.title("Consulta RENSPA desde SENASA")

# Introducción
st.markdown("""
Esta herramienta permite:

1. Consultar todos los RENSPA asociados a un CUIT en la base de datos de SENASA
2. Visualizar los polígonos de los campos en un mapa interactivo
3. Descargar los datos en formato KMZ/GeoJSON para su uso en sistemas GIS
""")

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
        st.warning("Para visualizar mapas, instala folium y streamlit-folium con: pip install folium streamlit-folium")
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
    
    # Añadir diferentes capas base
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                    name='Google Hybrid', 
                    attr='Google').add_to(m)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                    name='Google Satellite', 
                    attr='Google').add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    
    # Añadir herramienta de medición
    MeasureControl(position='topright', 
                  primary_length_unit='kilometers', 
                  secondary_length_unit='miles', 
                  primary_area_unit='hectares').add_to(m)
    
    # Añadir mini mapa para ubicación
    MiniMap().add_to(m)
    
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
                if incluir_poligono:
                    status_text.text("Obteniendo información de polígonos...")
                    progress_bar.progress(40)
                    
                    # Listas para almacenar resultados
                    poligonos_gee = []
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
                elif incluir_poligono and not folium_disponible:
                    st.warning("Para visualizar mapas, instala folium y streamlit-folium con: pip install folium streamlit-folium")
                
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

with tab2:
    st.header("Consulta por Lista de RENSPA")
    st.write("Ingrese los RENSPA que desea consultar directamente (sin necesidad de un CUIT).")

    # Opciones de entrada
    input_type = st.radio(
        "Seleccione método de entrada:",
        ["Ingresar manualmente", "Cargar archivo"],
        key="renspa_input_type"
    )

    renspa_list = []

    if input_type == "Ingresar manualmente":
        # Área de texto para ingresar múltiples RENSPA
        renspa_input = st.text_area(
            "Ingrese los RENSPA (uno por línea):", 
            "01.001.0.00123/01\n01.001.0.00456/02\n01.001.0.00789/03",
            height=150,
            key="renspa_list_input"
        )
        
        if renspa_input:
            renspa_list = [line.strip() for line in renspa_input.split('\n') if line.strip()]
    else:
        uploaded_file = st.file_uploader(
            "Suba un archivo TXT con un RENSPA por línea", 
            type=['txt'],
            key="renspa_file_upload"
        )
        
        if uploaded_file:
            content = uploaded_file.getvalue().decode('utf-8')
            renspa_list = [line.strip() for line in content.split('\n') if line.strip()]
            st.success(f"Archivo cargado con {len(renspa_list)} RENSPA")

    # Mostrar lista de RENSPA a procesar
    if renspa_list:
        st.write(f"RENSPA a procesar ({len(renspa_list)}):")
        st.write(", ".join(renspa_list[:10]) + ("..." if len(renspa_list) > 10 else ""))

    # Botón para procesar
    if st.button("Procesar Lista de RENSPA", key="btn_renspa_list") and renspa_list:
        with st.spinner('Procesando lista de RENSPA...'):
            # Crear barras de progreso
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Procesamiento para cada RENSPA
            poligonos_gee = []
            fallidos = []
            detalles_renspa = []
            
            for i, renspa in enumerate(renspa_list):
                # Actualizar progreso
                progress_percentage = (i * 70) // len(renspa_list)
                progress_bar.progress(progress_percentage)
                status_text.text(f"Procesando RENSPA: {renspa} ({i+1}/{len(renspa_list)})")
                
                try:
                    # Normalizar RENSPA
                    renspa_normalizado = normalizar_renspa(renspa)
                    
                    # Consultar detalles
                    resultado = consultar_renspa_detalle(renspa_normalizado)
                    
                    if resultado and 'items' in resultado and resultado['items']:
                        item = resultado['items'][0]
                        
                        # Extraer datos básicos
                        datos_renspa = {
                            'renspa': renspa_normalizado,
                            'titular': item.get('titular', ''),
                            'localidad': item.get('localidad', ''),
                            'superficie': item.get('superficie', 0),
                            'fecha_baja': item.get('fecha_baja', None)
                        }
                        
                        # Añadir a la lista de detalles
                        detalles_renspa.append(datos_renspa)
                        
                        # Extraer polígono si está disponible
                        if 'poligono' in item and item['poligono']:
                            poligono_str = item['poligono']
                            coordenadas = extraer_coordenadas(poligono_str)
                            
                            if coordenadas:
                                # Añadir coordenadas al diccionario
                                datos_renspa['coords'] = coordenadas
                                poligonos_gee.append(datos_renspa)
                                continue
                        
                        # Si llegamos aquí, no se pudo extraer el polígono
                        fallidos.append(renspa_normalizado)
                    else:
                        fallidos.append(renspa)
                
                except Exception as e:
                    st.error(f"Error procesando {renspa}: {str(e)}")
                    fallidos.append(renspa)
                
                # Pausa breve
                time.sleep(TIEMPO_ESPERA)
            
            # Crear DataFrame con todos los detalles
            df_renspa = pd.DataFrame(detalles_renspa)
            
            # Actualizar progreso
            status_text.text("Generando visualizaciones...")
            progress_bar.progress(80)
            
            # Mostrar estadísticas
            st.subheader("Resultados del procesamiento")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("RENSPA procesados", len(renspa_list))
            with col2:
                st.metric("RENSPA obtenidos", len(detalles_renspa))
            with col3:
                st.metric("RENSPA con polígono", len(poligonos_gee))
            
            # Mostrar datos en tabla
            st.subheader("Detalles de RENSPA")
            if not df_renspa.empty:
                st.dataframe(df_renspa)
            else:
                st.warning("No se pudo obtener información para ninguno de los RENSPA proporcionados.")
            
            # Panel de estadísticas
            if not df_renspa.empty:
                mostrar_estadisticas(df_renspa, poligonos_gee)
            
            # Visualizar en mapa
            if poligonos_gee and folium_disponible:
                st.subheader("Visualización de polígonos")
                
                # Crear mapa mejorado
                m = crear_mapa_mejorado(poligonos_gee)
                
                # Mostrar el mapa
                folium_static(m, width=1000, height=600)
                
                # Preparar archivos para descarga
                status_text.text("Preparando archivos para descarga...")
                progress_bar.progress(90)
                
                # Crear archivo KML
                kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>RENSPA - Lista personalizada</name>
  <description>Polígonos de RENSPA de la lista personalizada</description>
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
                            "superficie": pol['superficie']
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [pol['coords']]
                        }
                    }
                    geojson_data["features"].append(feature)
                
                geojson_str = json.dumps(geojson_data, indent=2)
                
                # Preparar CSV con todos los datos
                if not df_renspa.empty:
                    csv_data = df_renspa.to_csv(index=False).encode('utf-8')
                else:
                    csv_data = "No hay datos disponibles".encode('utf-8')
                
                # Opciones de descarga
                st.subheader("Descargar resultados")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.download_button(
                        label="Descargar KMZ",
                        data=kmz_buffer,
                        file_name="renspa_lista.kmz",
                        mime="application/vnd.google-earth.kmz",
                    )
                
                with col2:
                    st.download_button(
                        label="Descargar GeoJSON",
                        data=geojson_str,
                        file_name="renspa_lista.geojson",
                        mime="application/json",
                    )
                
                with col3:
                    st.download_button(
                        label="Descargar CSV",
                        data=csv_data,
                        file_name="renspa_lista.csv",
                        mime="text/csv",
                    )
            
            # Completar progreso
            status_text.text("Procesamiento completo!")
            progress_bar.progress(100)

with tab3:
    st.header("Consulta por Múltiples CUITs")
    st.write("Ingrese múltiples CUITs para procesar todos sus RENSPA de una vez.")

    # Opciones de entrada
    cuit_input_type = st.radio(
        "Seleccione método de entrada:",
        ["Ingresar manualmente", "Cargar archivo"],
        key="multi_cuit_input_type"
    )

    cuit_list = []

    if cuit_input_type == "Ingresar manualmente":
        # Área de texto para ingresar múltiples CUITs
        cuits_input = st.text_area(
            "Ingrese los CUITs (uno por línea):", 
            "30-65425756-2\n30-12345678-9",
            height=150,
            key="cuits_input"
        )
        
        if cuits_input:
            cuit_list = [line.strip() for line in cuits_input.split('\n') if line.strip()]
    else:
        cuit_file = st.file_uploader(
            "Suba un archivo TXT con un CUIT por línea", 
            type=['txt'], 
            key="cuit_file"
        )
        
        if cuit_file:
            content = cuit_file.getvalue().decode('utf-8')
            cuit_list = [line.strip() for line in content.split('\n') if line.strip()]
            st.success(f"Archivo cargado con {len(cuit_list)} CUITs")

    # Opciones adicionales
    col1, col2 = st.columns(2)
    with col1:
        multi_solo_activos = st.checkbox("Solo RENSPA activos", value=True, key="multi_solo_activos")
    with col2:
        multi_cuit_color = st.checkbox("Usar color diferente para cada CUIT", value=True, key="multi_cuit_color")

    # Botón para procesar
    if st.button("Procesar Múltiples CUITs", key="btn_multi_cuit") and cuit_list:
        with st.spinner('Procesando múltiples CUITs...'):
            # Crear barras de progreso
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Procesamiento para cada CUIT
            poligonos_gee = []
            todos_renspa = []
            cuits_normalizados = []
            cuit_colors = {}
            
            # Normalizar CUITs
            for cuit in cuit_list:
                try:
                    cuit_normalizado = normalizar_cuit(cuit)
                    cuits_normalizados.append(cuit_normalizado)
                    
                    # Asignar un color aleatorio para este CUIT
                    if multi_cuit_color:
                        r = random.randint(0, 200)
                        g = random.randint(0, 200)
                        b = random.randint(0, 200)
                        cuit_colors[cuit_normalizado] = f'#{r:02x}{g:02x}{b:02x}'
                except ValueError as e:
                    st.error(f"CUIT inválido: {cuit}. {str(e)}")
            
            # Verificar que haya CUITs válidos
            if not cuits_normalizados:
                st.error("No se proporcionaron CUITs válidos.")
                st.stop()
            
            # Procesar cada CUIT
            for i, cuit in enumerate(cuits_normalizados):
                # Actualizar progreso
                progress_percentage = (i * 70) // len(cuits_normalizados)
                progress_bar.progress(progress_percentage)
                status_text.text(f"Procesando CUIT: {cuit} ({i+1}/{len(cuits_normalizados)})")
                
                # Obtener todos los RENSPA para este CUIT
                renspa_cuit = obtener_renspa_por_cuit(cuit)
                
                if renspa_cuit:
                    # Añadir el CUIT a cada registro para identificación
                    for renspa in renspa_cuit:
                        renspa['cuit'] = cuit
                    
                    # Añadir a la lista total
                    todos_renspa.extend(renspa_cuit)
                    
                    # Filtrar por activos si se solicita
                    if multi_solo_activos:
                        renspa_a_procesar = [r for r in renspa_cuit if r.get('fecha_baja') is None]
                    else:
                        renspa_a_procesar = renspa_cuit
                    
                    # Procesar polígonos de este CUIT
                    for renspa_item in renspa_a_procesar:
                        renspa = renspa_item['renspa']
                        
                        # Verificar si ya tiene el polígono en la información básica
                        if 'poligono' in renspa_item and renspa_item['poligono']:
                            poligono_str = renspa_item['poligono']
                            superficie = renspa_item.get('superficie', 0)
                            
                            # Extraer coordenadas
                            coordenadas = extraer_coordenadas(poligono_str)
                            
                            if coordenadas:
                                # Crear objeto con datos del polígono
                                poligono_data = {
                                    'renspa': renspa,
                                    'coords': coordenadas,
                                    'superficie': superficie,
                                    'titular': renspa_item.get('titular', ''),
                                    'localidad': renspa_item.get('localidad', ''),
                                    'cuit': cuit
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
                                        'titular': renspa_item.get('titular', ''),
                                        'localidad': renspa_item.get('localidad', ''),
                                        'cuit': cuit
                                    }
                                    poligonos_gee.append(poligono_data)
                        
                        # Pausa breve para no sobrecargar la API
                        time.sleep(TIEMPO_ESPERA)
            
            # Crear DataFrame con todos los RENSPA
            df_renspa = pd.DataFrame(todos_renspa)
            
            # Actualizar progreso
            status_text.text("Generando visualizaciones...")
            progress_bar.progress(80)
            
            # Mostrar estadísticas
            st.subheader("Resultados del procesamiento")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("CUITs procesados", len(cuits_normalizados))
            with col2:
                st.metric("RENSPA obtenidos", len(todos_renspa))
            with col3:
                st.metric("RENSPA con polígono", len(poligonos_gee))
            
            # Mostrar datos en tabla
            st.subheader("Detalles de RENSPA")
            if not df_renspa.empty:
                st.dataframe(df_renspa)
            else:
                st.warning("No se pudo obtener información para ninguno de los CUITs proporcionados.")
            
            # Panel de estadísticas
            if not df_renspa.empty:
                mostrar_estadisticas(df_renspa, poligonos_gee)
            
            # Visualizar en mapa
            if poligonos_gee and folium_disponible:
                st.subheader("Visualización de polígonos")
                
                # Crear mapa mejorado con colores por CUIT
                m = crear_mapa_mejorado(poligonos_gee, cuit_colors=cuit_colors if multi_cuit_color else None)
                
                # Mostrar el mapa
                folium_static(m, width=1000, height=600)
                
                # Preparar archivos para descarga
                status_text.text("Preparando archivos para descarga...")
                progress_bar.progress(90)
                
                # Crear archivo KML
                kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>RENSPA - Múltiples CUITs</name>
  <description>Polígonos de RENSPA para múltiples CUITs</description>
"""
                
                # Añadir estilos para cada CUIT
                if multi_cuit_color:
                    for cuit, color in cuit_colors.items():
                        # Convertir color de hex a KML (aabbggrr)
                        color_hex = color.lstrip('#')
                        r = color_hex[0:2]
                        g = color_hex[2:4]
                        b = color_hex[4:6]
                        kml_color = f"7f{b}{g}{r}"  # 7f de transparencia
                        
                        cuit_clean = cuit.replace('-', '_')
                        kml_content += f"""
  <Style id="style_{cuit_clean}">
    <LineStyle>
      <color>ff{b}{g}{r}</color>
      <width>3</width>
    </LineStyle>
    <PolyStyle>
      <color>{kml_color}</color>
    </PolyStyle>
  </Style>
"""
                else:
                    # Estilo único para todos
                    kml_content += """
  <Style id="defaultStyle">
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
                    # Determinar estilo
                    if multi_cuit_color:
                        cuit_clean = pol['cuit'].replace('-', '_')
                        style_url = f"#style_{cuit_clean}"
                    else:
                        style_url = "#defaultStyle"
                    
                    kml_content += f"""
  <Placemark>
    <name>{pol['renspa']}</name>
    <description><![CDATA[
      <b>RENSPA:</b> {pol['renspa']}<br/>
      <b>CUIT:</b> {pol['cuit']}<br/>
      <b>Titular:</b> {pol['titular']}<br/>
      <b>Localidad:</b> {pol['localidad']}<br/>
      <b>Superficie:</b> {pol['superficie']} ha
    ]]></description>
    <styleUrl>{style_url}</styleUrl>
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
                            "cuit": pol['cuit'],
                            "titular": pol['titular'],
                            "localidad": pol['localidad'],
                            "superficie": pol['superficie']
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [pol['coords']]
                        }
                    }
                    geojson_data["features"].append(feature)
                
                geojson_str = json.dumps(geojson_data, indent=2)
                
                # Preparar CSV con todos los datos
                if not df_renspa.empty:
                    csv_data = df_renspa.to_csv(index=False).encode('utf-8')
                else:
                    csv_data = "No hay datos disponibles".encode('utf-8')
                
                # Opciones de descarga
                st.subheader("Descargar resultados")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.download_button(
                        label="Descargar KMZ",
                        data=kmz_buffer,
                        file_name="renspa_multiples_cuits.kmz",
                        mime="application/vnd.google-earth.kmz",
                    )
                
                with col2:
                    st.download_button(
                        label="Descargar GeoJSON",
                        data=geojson_str,
                        file_name="renspa_multiples_cuits.geojson",
                        mime="application/json",
                    )
                
                with col3:
                    st.download_button(
                        label="Descargar CSV",
                        data=csv_data,
                        file_name="renspa_multiples_cuits.csv",
                        mime="text/csv",
                    )
            
            # Completar progreso
            status_text.text("Procesamiento completo!")
            progress_bar.progress(100)

# Información en el pie de página
st.sidebar.markdown("---")
st.sidebar.info("Desarrollado para análisis agrícola en Argentina")


