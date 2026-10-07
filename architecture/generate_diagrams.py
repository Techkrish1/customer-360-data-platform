"""
Generates two draw.io diagram files:
  oltp_er_diagram.drawio    - PostgreSQL source schema (OLTP)
  olap_star_schema.drawio   - Gold layer star schema + mart (OLAP)
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

OUT_DIR = Path(__file__).parent / "diagrams"
OUT_DIR.mkdir(exist_ok=True)

# ── Shared XML builder ─────────────────────────────────────────────────────────

def new_graph(page_w=1400, page_h=900):
    model = ET.Element("mxGraphModel", {
        "dx": "1422", "dy": "762", "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
        "fold": "1", "page": "1", "pageScale": "1",
        "pageWidth": str(page_w), "pageHeight": str(page_h),
        "math": "0", "shadow": "0"
    })
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    return model, root


def table(root, tid, name, x, y, w, h, header_color="#dae8fc", text_color="#000000"):
    style = (
        f"shape=table;startSize=30;container=1;collapsible=0;childLayout=tableLayout;"
        f"fixedRows=1;rowLines=0;fontStyle=1;align=center;resizeLast=1;"
        f"fontSize=13;fillColor={header_color};strokeColor=#6c8ebf;"
        f"fontColor={text_color};"
    )
    cell = ET.SubElement(root, "mxCell", id=tid, value=name, style=style,
                         vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y),
                  width=str(w), height=str(h), **{"as": "geometry"})
    return cell


def row(root, rid, tid, y_offset, pk_fk, col_name, col_type,
        row_color="#ffffff", name_bold=False):
    row_style = (
        "shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;"
        f"fillColor={row_color};collapsible=0;dropTarget=0;"
        "points=[[0,0.5],[1,0.5]];portConstraint=eastwest;"
        "fontSize=11;top=0;left=0;right=0;bottom=1;"
    )
    r = ET.SubElement(root, "mxCell", id=rid, value="", style=row_style,
                      vertex="1", parent=tid)
    ET.SubElement(r, "mxGeometry", y=str(y_offset), width="260", height="26",
                  **{"as": "geometry"})

    # PK/FK badge
    badge_style = (
        "shape=partialRectangle;connectable=0;fillColor=none;"
        "top=0;left=0;bottom=0;right=0;fontStyle=1;overflow=hidden;"
        "fontSize=10;strokeColor=none;"
    )
    b = ET.SubElement(root, "mxCell", id=f"{rid}_b", value=pk_fk,
                      style=badge_style, vertex="1", connectable="0", parent=rid)
    ET.SubElement(b, "mxGeometry", width="38", height="26",
                  **{"as": "geometry"})
    ET.SubElement(b, "mxGeometry", width="38", height="26",
                  **{"as": "alternateBounds"})

    # Column name
    name_font = "4" if name_bold else "0"   # 4 = underline for PK
    name_style = (
        f"shape=partialRectangle;connectable=0;fillColor=none;"
        f"top=0;left=0;bottom=0;right=0;overflow=hidden;fontSize=11;"
        f"fontStyle={name_font};strokeColor=none;"
    )
    n = ET.SubElement(root, "mxCell", id=f"{rid}_n", value=col_name,
                      style=name_style, vertex="1", connectable="0", parent=rid)
    ET.SubElement(n, "mxGeometry", x="38", width="152", height="26",
                  **{"as": "geometry"})
    ET.SubElement(n, "mxGeometry", width="152", height="26",
                  **{"as": "alternateBounds"})

    # Data type
    type_style = (
        "shape=partialRectangle;connectable=0;fillColor=none;"
        "top=0;left=0;bottom=0;right=0;overflow=hidden;fontSize=10;"
        "fontStyle=2;align=right;strokeColor=none;fontColor=#666666;"
    )
    t = ET.SubElement(root, "mxCell", id=f"{rid}_t", value=col_type,
                      style=type_style, vertex="1", connectable="0", parent=rid)
    ET.SubElement(t, "mxGeometry", x="190", width="70", height="26",
                  **{"as": "geometry"})
    ET.SubElement(t, "mxGeometry", width="70", height="26",
                  **{"as": "alternateBounds"})
    return r


def edge(root, eid, src, tgt, label="", style=None):
    if style is None:
        style = (
            "edgeStyle=entityRelationEdgeStyle;endArrow=ERzeroToMany;"
            "startArrow=ERmandOne;exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
            "entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
            "fontSize=11;fontStyle=2;"
        )
    e = ET.SubElement(root, "mxCell", id=eid, value=label, style=style,
                      edge="1", source=src, target=tgt, parent="1")
    ET.SubElement(e, "mxGeometry", relative="1", **{"as": "geometry"})


def label_box(root, lid, text, x, y, w=200, h=30,
              font_size=16, bold=True, color="#000000"):
    fs = "1" if bold else "0"
    style = (
        f"text;html=1;align=center;verticalAlign=middle;resizable=0;"
        f"points=[];autosize=1;strokeColor=none;fillColor=none;"
        f"fontSize={font_size};fontStyle={fs};fontColor={color};"
    )
    c = ET.SubElement(root, "mxCell", id=lid, value=text, style=style,
                      vertex="1", parent="1")
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y),
                  width=str(w), height=str(h), **{"as": "geometry"})


def save(model, path):
    raw = ET.tostring(model, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    # remove the extra xml declaration minidom adds
    lines = pretty.split("\n")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    print(f"  Saved: {path}")


# ── OLTP ER Diagram ────────────────────────────────────────────────────────────

def build_oltp():
    model, root = new_graph(page_w=1300, page_h=780)

    TW = 260   # table width
    RH = 26    # row height
    HEADER = 30

    # ── retailco_customers ──
    CUST_COLS = [
        ("PK", "customer_id",  "BIGINT"),
        ("",   "email",        "VARCHAR"),
        ("",   "name",         "VARCHAR"),
        ("",   "region",       "VARCHAR"),
        ("",   "tier",         "VARCHAR"),
        ("",   "created_at",   "TIMESTAMP"),
        ("",   "updated_at",   "TIMESTAMP"),
    ]
    cx, cy = 60, 200
    table(root, "cust", "retailco_customers", cx, cy, TW,
          HEADER + len(CUST_COLS)*RH, header_color="#dae8fc")
    for i, (pk, col, typ) in enumerate(CUST_COLS):
        row(root, f"cust_r{i}", "cust", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── retailco_orders ──
    ORD_COLS = [
        ("PK", "order_id",      "BIGINT"),
        ("FK", "customer_id",   "BIGINT"),
        ("",   "status",        "VARCHAR"),
        ("",   "total_amount",  "DECIMAL"),
        ("",   "region",        "VARCHAR"),
        ("",   "created_at",    "TIMESTAMP"),
        ("",   "updated_at",    "TIMESTAMP"),
    ]
    ox, oy = 430, 200
    table(root, "ord", "retailco_orders", ox, oy, TW,
          HEADER + len(ORD_COLS)*RH, header_color="#dae8fc")
    for i, (pk, col, typ) in enumerate(ORD_COLS):
        row(root, f"ord_r{i}", "ord", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── retailco_order_items ──
    ITEM_COLS = [
        ("PK", "item_id",    "BIGINT"),
        ("FK", "order_id",   "BIGINT"),
        ("",   "product_id", "BIGINT"),
        ("",   "quantity",   "INT"),
        ("",   "unit_price", "DECIMAL"),
        ("",   "created_at", "TIMESTAMP"),
        ("",   "updated_at", "TIMESTAMP"),
    ]
    ix, iy = 800, 200
    table(root, "items", "retailco_order_items", ix, iy, TW,
          HEADER + len(ITEM_COLS)*RH, header_color="#dae8fc")
    for i, (pk, col, typ) in enumerate(ITEM_COLS):
        row(root, f"item_r{i}", "items", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── retailco_pipeline_watermarks ──
    WM_COLS = [
        ("PK", "pipeline_name",  "VARCHAR"),
        ("",   "last_watermark", "TIMESTAMP"),
        ("",   "last_run_at",    "TIMESTAMP"),
        ("",   "status",         "VARCHAR"),
    ]
    wx, wy = 60, 530
    table(root, "wm", "retailco_pipeline_watermarks", wx, wy, TW,
          HEADER + len(WM_COLS)*RH, header_color="#f8cecc")
    for i, (pk, col, typ) in enumerate(WM_COLS):
        row(root, f"wm_r{i}", "wm", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── Relationships ──
    edge(root, "e1", "cust", "ord",
         style="edgeStyle=entityRelationEdgeStyle;endArrow=ERzeroToMany;"
               "startArrow=ERmandOne;exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
               "entryX=0;entryY=0.5;entryDx=0;entryDy=0;fontSize=11;")
    edge(root, "e2", "ord", "items",
         style="edgeStyle=entityRelationEdgeStyle;endArrow=ERzeroToMany;"
               "startArrow=ERmandOne;exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
               "entryX=0;entryY=0.5;entryDx=0;entryDy=0;fontSize=11;")

    # ── Labels ──
    label_box(root, "title", "OLTP Source Schema — PostgreSQL",
              350, 60, w=400, h=36, font_size=18)
    label_box(root, "lbl_1to_m1", "1",  395, 300, w=20, h=20,
              font_size=12, bold=True, color="#6c8ebf")
    label_box(root, "lbl_m1",     "M",  410, 300, w=20, h=20,
              font_size=12, bold=True, color="#6c8ebf")
    label_box(root, "lbl_1to_m2", "1",  765, 300, w=20, h=20,
              font_size=12, bold=True, color="#6c8ebf")
    label_box(root, "lbl_m2",     "M",  780, 300, w=20, h=20,
              font_size=12, bold=True, color="#6c8ebf")
    label_box(root, "wm_note",
              "Tracks pipeline watermark\n(not part of business data)",
              60, 490, w=260, h=30, font_size=10, bold=False, color="#c00000")

    save(model, OUT_DIR / "oltp_er_diagram.drawio")


# ── OLAP Star Schema ──────────────────────────────────────────────────────────

def build_olap():
    model, root = new_graph(page_w=1600, page_h=1000)

    TW = 270
    RH = 24
    HEADER = 30

    # ── dim_customer (left) ──
    DC_COLS = [
        ("PK", "customer_key",   "BIGINT"),
        ("",   "customer_id",    "BIGINT"),
        ("",   "name",           "VARCHAR"),
        ("",   "email",          "VARCHAR"),
        ("",   "region",         "VARCHAR"),
        ("",   "tier",           "VARCHAR"),
        ("",   "is_current",     "BOOLEAN"),
        ("",   "effective_from", "TIMESTAMP"),
        ("",   "dw_inserted_at", "TIMESTAMP"),
    ]
    table(root, "dc", "dim_customer", 60, 320, TW,
          HEADER + len(DC_COLS)*RH, header_color="#d5e8d4")
    for i, (pk, col, typ) in enumerate(DC_COLS):
        row(root, f"dc_r{i}", "dc", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── dim_date (top center) ──
    DD_COLS = [
        ("PK", "date_key",     "INT"),
        ("",   "full_date",    "DATE"),
        ("",   "day_of_month", "INT"),
        ("",   "day_name",     "VARCHAR"),
        ("",   "week_of_year", "INT"),
        ("",   "month_number", "INT"),
        ("",   "month_name",   "VARCHAR"),
        ("",   "quarter",      "INT"),
        ("",   "year",         "INT"),
        ("",   "is_weekend",   "BOOLEAN"),
    ]
    table(root, "dd", "dim_date", 560, 40, TW,
          HEADER + len(DD_COLS)*RH, header_color="#d5e8d4")
    for i, (pk, col, typ) in enumerate(DD_COLS):
        row(root, f"dd_r{i}", "dd", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── dim_product (right) ──
    DP_COLS = [
        ("PK", "product_key",    "BIGINT"),
        ("",   "product_id",     "BIGINT"),
        ("",   "product_name",   "VARCHAR"),
        ("",   "category",       "VARCHAR"),
        ("",   "is_active",      "BOOLEAN"),
        ("",   "dw_inserted_at", "TIMESTAMP"),
    ]
    table(root, "dp", "dim_product", 1060, 320, TW,
          HEADER + len(DP_COLS)*RH, header_color="#d5e8d4")
    for i, (pk, col, typ) in enumerate(DP_COLS):
        row(root, f"dp_r{i}", "dp", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── fact_orders (center) ──
    FO_COLS = [
        ("PK", "order_key",      "BIGINT"),
        ("",   "order_id",       "BIGINT"),
        ("FK", "customer_key",   "BIGINT"),
        ("FK", "date_key",       "INT"),
        ("",   "status",         "VARCHAR"),
        ("",   "total_amount",   "DECIMAL"),
        ("",   "item_count",     "INT"),
        ("",   "region",         "VARCHAR"),
        ("",   "created_at",     "TIMESTAMP"),
        ("",   "dw_inserted_at", "TIMESTAMP"),
    ]
    table(root, "fo", "fact_orders", 560, 380, TW,
          HEADER + len(FO_COLS)*RH, header_color="#ffe6cc")
    for i, (pk, col, typ) in enumerate(FO_COLS):
        row(root, f"fo_r{i}", "fo", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── fact_order_items (bottom center) ──
    FI_COLS = [
        ("PK", "item_key",       "BIGINT"),
        ("",   "item_id",        "BIGINT"),
        ("",   "order_id",       "BIGINT"),
        ("FK", "customer_key",   "BIGINT"),
        ("FK", "product_key",    "BIGINT"),
        ("FK", "date_key",       "INT"),
        ("",   "quantity",       "INT"),
        ("",   "unit_price",     "DECIMAL"),
        ("",   "line_total",     "DECIMAL"),
        ("",   "dw_inserted_at", "TIMESTAMP"),
    ]
    table(root, "fi", "fact_order_items", 560, 710, TW,
          HEADER + len(FI_COLS)*RH, header_color="#ffe6cc")
    for i, (pk, col, typ) in enumerate(FI_COLS):
        row(root, f"fi_r{i}", "fi", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── mart_customer_rfm (far right) ──
    MART_COLS = [
        ("PK", "customer_key",       "BIGINT"),
        ("",   "customer_id",        "BIGINT"),
        ("",   "name",               "VARCHAR"),
        ("",   "email",              "VARCHAR"),
        ("",   "region",             "VARCHAR"),
        ("",   "tier",               "VARCHAR"),
        ("",   "first_order_date",   "TIMESTAMP"),
        ("",   "last_order_date",    "TIMESTAMP"),
        ("",   "recency_days",       "INT"),
        ("",   "total_orders",       "INT"),
        ("",   "total_spent",        "DECIMAL"),
        ("",   "avg_order_value",    "DECIMAL"),
        ("",   "total_items",        "INT"),
        ("",   "r_score",            "INT"),
        ("",   "f_score",            "INT"),
        ("",   "m_score",            "INT"),
        ("",   "rfm_score",          "VARCHAR"),
        ("",   "rfm_segment",        "VARCHAR"),
        ("",   "churn_risk",         "VARCHAR"),
        ("",   "pipeline_updated_at","TIMESTAMP"),
    ]
    table(root, "mart", "mart_customer_rfm", 1360, 200, TW,
          HEADER + len(MART_COLS)*RH, header_color="#e1d5e7")
    for i, (pk, col, typ) in enumerate(MART_COLS):
        row(root, f"mart_r{i}", "mart", HEADER + i*RH, pk, col, typ,
            name_bold=(pk == "PK"))

    # ── Fact-to-Dimension edges ──
    def fact_dim_edge(eid, src, tgt, ex, ey, nx, ny):
        style = (
            f"edgeStyle=orthogonalEdgeStyle;endArrow=ERmany;startArrow=ERmandOne;"
            f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
            f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
            f"strokeColor=#82b366;strokeWidth=1.5;fontSize=10;"
        )
        e = ET.SubElement(root, "mxCell", id=eid, value="", style=style,
                          edge="1", source=src, target=tgt, parent="1")
        ET.SubElement(e, "mxGeometry", relative="1", **{"as": "geometry"})

    # fact_orders → dim_customer
    fact_dim_edge("e_fo_dc", "fo", "dc", 0, 0.4, 1, 0.4)
    # fact_orders → dim_date
    fact_dim_edge("e_fo_dd", "fo", "dd", 0.5, 0, 0.5, 1)
    # fact_order_items → dim_customer
    fact_dim_edge("e_fi_dc", "fi", "dc", 0, 0.4, 1, 0.6)
    # fact_order_items → dim_product
    fact_dim_edge("e_fi_dp", "fi", "dp", 1, 0.4, 0, 0.4)
    # fact_order_items → dim_date
    fact_dim_edge("e_fi_dd", "fi", "dd", 0.5, 0, 0.3, 1)

    # mart ← fact_orders (aggregated from)
    mart_style = (
        "edgeStyle=orthogonalEdgeStyle;endArrow=open;startArrow=none;"
        "exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
        "entryX=0;entryY=0.4;entryDx=0;entryDy=0;"
        "strokeColor=#9673a6;strokeWidth=2;dashed=1;fontSize=10;"
    )
    e_mart = ET.SubElement(root, "mxCell", id="e_mart", value="aggregated from",
                           style=mart_style, edge="1",
                           source="fo", target="mart", parent="1")
    ET.SubElement(e_mart, "mxGeometry", relative="1", **{"as": "geometry"})

    # ── Labels ──
    label_box(root, "title",
              "OLAP Star Schema — Gold Layer (Delta Lake on S3)",
              420, 10, w=560, h=36, font_size=18)
    label_box(root, "lbl_dim",  "DIMENSION TABLE",
              62,  290, w=270, h=22, font_size=10, bold=True, color="#82b366")
    label_box(root, "lbl_dim2", "DIMENSION TABLE",
              1062, 290, w=270, h=22, font_size=10, bold=True, color="#82b366")
    label_box(root, "lbl_dim3", "DIMENSION TABLE",
              562, 10, w=270, h=22, font_size=10, bold=True, color="#82b366")
    label_box(root, "lbl_fact1", "FACT TABLE",
              562, 350, w=270, h=22, font_size=10, bold=True, color="#d6790a")
    label_box(root, "lbl_fact2", "FACT TABLE",
              562, 680, w=270, h=22, font_size=10, bold=True, color="#d6790a")
    label_box(root, "lbl_mart",  "ANALYTICS MART",
              1362, 170, w=270, h=22, font_size=10, bold=True, color="#6a2c91")
    label_box(root, "scd_note",
              "SCD Type 1\n(Type 2 in v2)",
              62, 540, w=270, h=36, font_size=9, bold=False, color="#666666")
    label_box(root, "mart_note",
              "Pre-aggregated for Power BI\nNo joins at query time",
              1362, 680, w=270, h=36, font_size=9, bold=False, color="#666666")

    save(model, OUT_DIR / "olap_star_schema.drawio")


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating draw.io diagrams...")
    build_oltp()
    build_olap()
    print()
    print("Open in VS Code with the draw.io extension:")
    print("  architecture/diagrams/oltp_er_diagram.drawio")
    print("  architecture/diagrams/olap_star_schema.drawio")
