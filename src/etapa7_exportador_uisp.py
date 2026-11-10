"""
src/etapa7_exportador_uisp.py - Exportador KML para o Ubiquiti ISP Design Center (ispdesign.ui.com).
Gera nós (Sites/Torres com altura configurada) e linhas (PtP Links com metadados de rádio).
"""
import json
import os
import xml.etree.ElementTree as ET


def criar_kml_uisp(todos_sitios: list[dict], enlaces: list[dict], caminho_saida: str):
    kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(kml, "Document")
    
    # Metadados do Projeto
    nome_doc = ET.SubElement(document, "name")
    nome_doc.text = "Projeto SMP Seridó - Backhaul PTP"
    
    # Estilos de Ícones e Linhas
    estilos = {
        "estilo_erb": {"cor_icone": "ff00aaff", "escala": "1.1"},       # Laranja
        "estilo_ccc": {"cor_icone": "ff0000ff", "escala": "1.4"},       # Vermelho destacado
        "estilo_rep": {"cor_icone": "ffffff00", "escala": "1.3"},       # Ciano/Amarelo
        "linha_tronco": {"cor": "ff00aaff", "largura": "3.5"},
        "linha_local": {"cor": "ffaaaaaa", "largura": "2.0"}
    }
    
    for id_estilo, props in estilos.items():
        style = ET.SubElement(document, "Style", id=id_estilo)
        if "cor_icone" in props:
            icon_style = ET.SubElement(style, "IconStyle")
            color = ET.SubElement(icon_style, "color")
            color.text = props["cor_icone"]
            scale = ET.SubElement(icon_style, "scale")
            scale.text = props["escala"]
        if "cor" in props:
            line_style = ET.SubElement(style, "LineStyle")
            color = ET.SubElement(line_style, "color")
            color.text = props["cor"]
            width = ET.SubElement(line_style, "width")
            width.text = props["largura"]

    # Pasta 1: Sítios / Torres (Points)
    pasta_sitios = ET.SubElement(document, "Folder")
    nome_pasta_s = ET.SubElement(pasta_sitios, "name")
    nome_pasta_s.text = "Sítios e Torres (ERBs / CCC / Repetidoras)"

    mapa_coords = {}

    for s in todos_sitios:
        mapa_coords[s["id"]] = (s["longitude"], s["latitude"], s["altura_torre_m"])
        
        placemark = ET.SubElement(pasta_sitios, "Placemark")
        name = ET.SubElement(placemark, "name")
        name.text = s["nome"]
        
        desc = ET.SubElement(placemark, "description")
        desc.text = (
            f"ID: {s['id']}\n"
            f"Tipo: {s['tipo']}\n"
            f"Cidade: {s.get('cidade', 'Interurbano')}\n"
            f"Altura da Torre: {s['altura_torre_m']} m\n"
            f"Altitude do Terreno: {s.get('altitude_terreno_m', 0)} m"
        )
        
        style_url = ET.SubElement(placemark, "styleUrl")
        if "CCC" in s["tipo"]:
            style_url.text = "#estilo_ccc"
        elif "REPETIDORA" in s["tipo"]:
            style_url.text = "#estilo_rep"
        else:
            style_url.text = "#estilo_erb"
            
        point = ET.SubElement(placemark, "Point")
        # No KML, elevação relativa ao solo
        alt_mode = ET.SubElement(point, "altitudeMode")
        alt_mode.text = "relativeToGround"
        coordinates = ET.SubElement(point, "coordinates")
        coordinates.text = f"{s['longitude']},{s['latitude']},{s['altura_torre_m']}"

    # Pasta 2: Enlaces Ponto a Ponto (LineStrings)
    pasta_links = ET.SubElement(document, "Folder")
    nome_pasta_l = ET.SubElement(pasta_links, "name")
    nome_pasta_l.text = "Enlaces PTP de Micro-ondas"

    for l in enlaces:
        id_a, id_b = l["id_origem"], l["id_destino"]
        if id_a not in mapa_coords or id_b not in mapa_coords:
            continue
            
        coord_a = mapa_coords[id_a]
        coord_b = mapa_coords[id_b]
        
        placemark = ET.SubElement(pasta_links, "Placemark")
        name = ET.SubElement(placemark, "name")
        name.text = f"PTP: {l['origem']} <-> {l['destino']}"
        
        desc = ET.SubElement(placemark, "description")
        desc.text = (
            f"Distância: {l['distancia_km']} km\n"
            f"Antena Tx: {l.get('diametro_tx_m', 0.6)}m ({l.get('part_tx', 'Standard')})\n"
            f"Antena Rx: {l.get('diametro_rx_m', 0.6)}m ({l.get('part_rx', 'Standard')})\n"
            f"Torres (Tx / Rx): {l.get('h_torre_origem_m', 30)}m / {l.get('h_torre_destino_m', 30)}m\n"
            f"Fade Margin Estimada: {l.get('fade_margin_db', 30)} dB\n"
            f"RSL Estimado: {l.get('rsl_dbm', -40)} dBm"
        )
        
        style_url = ET.SubElement(placemark, "styleUrl")
        eh_tronco = "Serra" in l["origem"] or "Serra" in l["destino"] or "CCC" in l["origem"] or "CCC" in l["destino"]
        style_url.text = "#linha_tronco" if eh_tronco else "#linha_local"
        
        line_string = ET.SubElement(placemark, "LineString")
        alt_mode = ET.SubElement(line_string, "altitudeMode")
        alt_mode.text = "relativeToGround"
        coordinates = ET.SubElement(line_string, "coordinates")
        coordinates.text = (
            f"{coord_a[0]},{coord_a[1]},{coord_a[2]} "
            f"{coord_b[0]},{coord_b[1]},{coord_b[2]}"
        )

    # Serialização do XML
    tree = ET.ElementTree(kml)
    ET.indent(tree, space="  ", level=0)
    tree.write(caminho_saida, encoding="utf-8", xml_declaration=True)


def executar_etapa7(
    arquivo_sitios: str = "outputs/todos_sitios.json",
    arquivo_enlaces: str = "outputs/enlaces_com_antenas.json",
    saida_kml: str = "outputs/backhaul_serido_uisp.kml"
):
    if not os.path.exists(arquivo_sitios):
        arquivo_sitios = "todos_sitios.json"
    if not os.path.exists(arquivo_enlaces):
        arquivo_enlaces = "enlaces_com_antenas.json"

    with open(arquivo_sitios, "r", encoding="utf-8") as f:
        sitios = json.load(f)
    with open(arquivo_enlaces, "r", encoding="utf-8") as f:
        enlaces = json.load(f)

    os.makedirs("outputs", exist_ok=True)
    criar_kml_uisp(sitios, enlaces, saida_kml)

    print("=" * 95)
    print("ETAPA 7: EXPORTAÇÃO PARA O UBIQUITI ISP DESIGN CENTER (ispdesign.ui.com)")
    print("=" * 95)
    print(f"Total de Sítios/Torres processados: {len(sitios)}")
    print(f"Total de Enlaces PTP mapeados:       {len(enlaces)}")
    print(f"Arquivo KML gerado:                 '{saida_kml}'")
    print("=" * 95)


if __name__ == "__main__":
    executar_etapa7()