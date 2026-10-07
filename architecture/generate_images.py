"""
Generates PNG diagram images for OLTP ER diagram and OLAP Star Schema.
Output: architecture/diagrams/oltp_er_diagram.png
        architecture/diagrams/olap_star_schema.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from pathlib import Path

OUT_DIR = Path(__file__).parent / "diagrams"
OUT_DIR.mkdir(exist_ok=True)

# ── Color palette ──────────────────────────────────────────────────────────────
C = {
    "oltp_header" : "#4472C4",
    "oltp_row"    : "#EEF3FB",
    "oltp_row_alt": "#D9E4F5",
    "oltp_pk"     : "#1F4E79",
    "fact_header" : "#E67E22",
    "fact_row"    : "#FEF3E8",
    "fact_row_alt": "#FCDDB8",
    "dim_header"  : "#27AE60",
    "dim_row"     : "#EAFAF1",
    "dim_row_alt" : "#C8EDDA",
    "mart_header" : "#8E44AD",
    "mart_row"    : "#F5EEF8",
    "mart_row_alt": "#DFC7EE",
    "wm_header"   : "#C0392B",
    "wm_row"      : "#FDEDEC",
    "wm_row_alt"  : "#FAD7D3",
    "white"       : "#FFFFFF",
    "border"      : "#555555",
    "arrow"       : "#2C3E50",
    "text_white"  : "#FFFFFF",
    "text_dark"   : "#1A1A1A",
    "text_type"   : "#666666",
    "text_fk"     : "#C0392B",
    "text_pk"     : "#1F4E79",
    "bg"          : "#F8F9FA",
}

ROW_H   = 0.32
HEADER_H= 0.44
COL_W   = 2.6


# ── Draw a single table ────────────────────────────────────────────────────────

def draw_table(ax, x, y, title, columns, header_color, row_color, row_alt,
               col_w=COL_W):
    """
    columns: list of (badge, name, type)
    badge:  'PK', 'FK', or ''
    Returns bottom y coordinate.
    """
    n = len(columns)
    total_h = HEADER_H + n * ROW_H

    # Shadow
    shadow = mpatches.FancyBboxPatch(
        (x + 0.05, y - total_h - 0.05), col_w, total_h,
        boxstyle="round,pad=0.02", linewidth=0,
        facecolor="#CCCCCC", zorder=1)
    ax.add_patch(shadow)

    # Header
    hdr = mpatches.FancyBboxPatch(
        (x, y - HEADER_H), col_w, HEADER_H,
        boxstyle="round,pad=0.02", linewidth=1.2,
        edgecolor=C["border"], facecolor=header_color, zorder=2)
    ax.add_patch(hdr)
    ax.text(x + col_w / 2, y - HEADER_H / 2, title,
            ha="center", va="center", fontsize=9.5, fontweight="bold",
            color=C["text_white"], zorder=3)

    # Rows
    for i, (badge, name, dtype) in enumerate(columns):
        ry = y - HEADER_H - (i + 1) * ROW_H
        bg = row_alt if i % 2 == 0 else row_color
        rect = mpatches.Rectangle(
            (x, ry), col_w, ROW_H,
            linewidth=0.6, edgecolor="#CCCCCC", facecolor=bg, zorder=2)
        ax.add_patch(rect)

        # Badge (PK / FK)
        badge_color = C["text_pk"] if badge == "PK" else C["text_fk"]
        if badge:
            ax.text(x + 0.12, ry + ROW_H / 2, badge,
                    ha="left", va="center", fontsize=7, fontweight="bold",
                    color=badge_color, zorder=3)

        # Column name
        name_weight = "bold" if badge == "PK" else "normal"
        name_color  = C["text_pk"] if badge == "PK" else (
                      C["text_fk"] if badge == "FK" else C["text_dark"])
        ax.text(x + 0.5, ry + ROW_H / 2, name,
                ha="left", va="center", fontsize=8, fontweight=name_weight,
                color=name_color, zorder=3)

        # Data type
        ax.text(x + col_w - 0.08, ry + ROW_H / 2, dtype,
                ha="right", va="center", fontsize=7, fontstyle="italic",
                color=C["text_type"], zorder=3)

    # Bottom border
    ax.add_patch(mpatches.Rectangle(
        (x, y - total_h), col_w, total_h,
        linewidth=1.2, edgecolor=C["border"], facecolor="none", zorder=4))

    return y - total_h


def arrow(ax, x1, y1, x2, y2, color="#2C3E50", style="->", lw=1.5, dashed=False):
    ls = (0, (5, 4)) if dashed else "solid"
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle=style, color=color,
                    lw=lw, linestyle=ls,
                    connectionstyle="arc3,rad=0.0"),
                zorder=5)


def connector(ax, x1, y1, x2, y2, color="#2C3E50", lw=1.5, dashed=False):
    ls = "--" if dashed else "-"
    ax.plot([x1, x2], [y1, y2], color=color, lw=lw,
            linestyle=ls, zorder=5, solid_capstyle="round")


# ── OLTP ER Diagram ────────────────────────────────────────────────────────────

def build_oltp():
    fig, ax = plt.subplots(figsize=(18, 10))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 18)
    ax.set_ylim(-9.5, 1.2)
    ax.axis("off")

    # Title
    ax.text(9, 0.9, "OLTP Source Schema  —  PostgreSQL",
            ha="center", va="center", fontsize=15, fontweight="bold",
            color="#1A1A1A")
    ax.text(9, 0.5, "Transactional database powering the retail application",
            ha="center", va="center", fontsize=10, color="#555555")

    # ── retailco_customers ──
    CUST = [
        ("PK", "customer_id",  "BIGINT"),
        ("",   "email",        "VARCHAR"),
        ("",   "name",         "VARCHAR"),
        ("",   "region",       "VARCHAR"),
        ("",   "tier",         "VARCHAR"),
        ("",   "created_at",   "TIMESTAMP"),
        ("",   "updated_at",   "TIMESTAMP"),
    ]
    cx = 1.2
    draw_table(ax, cx, 0.0, "retailco_customers",
               CUST, C["oltp_header"], C["oltp_row"], C["oltp_row_alt"])

    # ── retailco_orders ──
    ORD = [
        ("PK", "order_id",     "BIGINT"),
        ("FK", "customer_id",  "BIGINT"),
        ("",   "status",       "VARCHAR"),
        ("",   "total_amount", "DECIMAL"),
        ("",   "region",       "VARCHAR"),
        ("",   "created_at",   "TIMESTAMP"),
        ("",   "updated_at",   "TIMESTAMP"),
    ]
    ox = 7.4
    draw_table(ax, ox, 0.0, "retailco_orders",
               ORD, C["oltp_header"], C["oltp_row"], C["oltp_row_alt"])

    # ── retailco_order_items ──
    ITEMS = [
        ("PK", "item_id",    "BIGINT"),
        ("FK", "order_id",   "BIGINT"),
        ("",   "product_id", "BIGINT"),
        ("",   "quantity",   "INT"),
        ("",   "unit_price", "DECIMAL"),
        ("",   "created_at", "TIMESTAMP"),
        ("",   "updated_at", "TIMESTAMP"),
    ]
    itx = 13.6
    draw_table(ax, itx, 0.0, "retailco_order_items",
               ITEMS, C["oltp_header"], C["oltp_row"], C["oltp_row_alt"])

    # ── retailco_pipeline_watermarks ──
    WM = [
        ("PK", "pipeline_name",  "VARCHAR"),
        ("",   "last_watermark", "TIMESTAMP"),
        ("",   "last_run_at",    "TIMESTAMP"),
        ("",   "status",         "VARCHAR"),
    ]
    draw_table(ax, 1.2, -5.2, "retailco_pipeline_watermarks",
               WM, C["wm_header"], C["wm_row"], C["wm_row_alt"])

    # ── Relationship arrows ──
    # customers → orders  (1 to many)
    mid_cust_right_y = -0.44 - 3 * ROW_H   # mid-height of customers table
    mid_ord_left_y   = -0.44 - 3 * ROW_H
    connector(ax, cx + COL_W, mid_cust_right_y, ox, mid_ord_left_y,
              color=C["arrow"], lw=2)

    # Cardinality labels
    ax.text(cx + COL_W + 0.15, mid_cust_right_y + 0.15, "1",
            fontsize=10, fontweight="bold", color=C["arrow"])
    ax.text(ox - 0.3, mid_ord_left_y + 0.15, "M",
            fontsize=10, fontweight="bold", color=C["arrow"])

    # orders → order_items  (1 to many)
    mid_ord_right_y  = -0.44 - 3 * ROW_H
    mid_item_left_y  = -0.44 - 3 * ROW_H
    connector(ax, ox + COL_W, mid_ord_right_y, itx, mid_item_left_y,
              color=C["arrow"], lw=2)
    ax.text(ox + COL_W + 0.15, mid_ord_right_y + 0.15, "1",
            fontsize=10, fontweight="bold", color=C["arrow"])
    ax.text(itx - 0.3, mid_item_left_y + 0.15, "M",
            fontsize=10, fontweight="bold", color=C["arrow"])

    # Watermarks note
    ax.text(1.2 + COL_W / 2, -5.2 + 0.25,
            "",  ha="center", fontsize=8, color=C["text_type"])
    ax.text(1.2 + COL_W / 2, -9.1,
            "Stores pipeline state (last watermark timestamp).\n"
            "Not business data — used only by extract_bronze.py.",
            ha="center", va="center", fontsize=8.5, color="#C0392B",
            style="italic")

    # Legend
    for i, (label, color) in enumerate([
        ("Primary Key (PK)", C["text_pk"]),
        ("Foreign Key (FK)", C["text_fk"]),
    ]):
        ax.text(13.6 + i * 2.5, -9.0, f"■  {label}",
                fontsize=8.5, color=color, fontweight="bold")

    plt.tight_layout(pad=0.5)
    out = OUT_DIR / "oltp_er_diagram.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ── OLAP Star Schema ──────────────────────────────────────────────────────────

def build_olap():
    fig, ax = plt.subplots(figsize=(22, 14))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, 22)
    ax.set_ylim(-13, 1.5)
    ax.axis("off")

    # Title
    ax.text(11, 1.3, "OLAP Star Schema  —  Gold Layer  (Delta Lake on S3)",
            ha="center", va="center", fontsize=16, fontweight="bold", color="#1A1A1A")
    ax.text(11, 0.85, "Hosted in Databricks Unity Catalog  ·  workspace.customer360",
            ha="center", va="center", fontsize=10, color="#555555")

    DW = COL_W + 0.2   # slightly wider for OLAP tables

    # ── dim_customer (left) ──
    DC = [
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
    dc_x, dc_y = 0.5, 0.4
    draw_table(ax, dc_x, dc_y, "dim_customer",
               DC, C["dim_header"], C["dim_row"], C["dim_row_alt"], col_w=DW)
    ax.text(dc_x + DW/2, dc_y - HEADER_H - len(DC)*ROW_H - 0.22,
            "SCD Type 1  (Type 2 in v2)",
            ha="center", fontsize=7.5, color="#27AE60", style="italic")

    # ── dim_date (top center) ──
    DD = [
        ("PK", "date_key",     "INT"),
        ("",   "full_date",    "DATE"),
        ("",   "day_of_month", "INT"),
        ("",   "day_name",     "VARCHAR"),
        ("",   "week_of_year", "INT"),
        ("",   "month_name",   "VARCHAR"),
        ("",   "quarter",      "INT"),
        ("",   "year",         "INT"),
        ("",   "is_weekend",   "BOOLEAN"),
    ]
    dd_x, dd_y = 8.0, 0.4
    draw_table(ax, dd_x, dd_y, "dim_date",
               DD, C["dim_header"], C["dim_row"], C["dim_row_alt"], col_w=DW)

    # ── dim_product (right) ──
    DP = [
        ("PK", "product_key",    "BIGINT"),
        ("",   "product_id",     "BIGINT"),
        ("",   "product_name",   "VARCHAR"),
        ("",   "category",       "VARCHAR"),
        ("",   "is_active",      "BOOLEAN"),
        ("",   "dw_inserted_at", "TIMESTAMP"),
    ]
    dp_x, dp_y = 15.2, 0.4
    draw_table(ax, dp_x, dp_y, "dim_product",
               DP, C["dim_header"], C["dim_row"], C["dim_row_alt"], col_w=DW)

    # ── fact_orders (center top-ish) ──
    FO = [
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
    fo_x, fo_y = 8.0, -4.0
    draw_table(ax, fo_x, fo_y, "fact_orders",
               FO, C["fact_header"], C["fact_row"], C["fact_row_alt"], col_w=DW)

    # ── fact_order_items (center bottom) ──
    FI = [
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
    fi_x, fi_y = 8.0, -8.2
    draw_table(ax, fi_x, fi_y, "fact_order_items",
               FI, C["fact_header"], C["fact_row"], C["fact_row_alt"], col_w=DW)

    # ── mart_customer_rfm (far right) ──
    MART = [
        ("PK", "customer_key",        "BIGINT"),
        ("",   "name  /  email",      "VARCHAR"),
        ("",   "region  /  tier",     "VARCHAR"),
        ("",   "first_order_date",    "TIMESTAMP"),
        ("",   "last_order_date",     "TIMESTAMP"),
        ("",   "recency_days",        "INT"),
        ("",   "total_orders",        "INT"),
        ("",   "total_spent",         "DECIMAL"),
        ("",   "avg_order_value",     "DECIMAL"),
        ("",   "total_items",         "INT"),
        ("",   "r_score / f_score / m_score", "INT"),
        ("",   "rfm_score",           "VARCHAR"),
        ("",   "rfm_segment",         "VARCHAR"),
        ("",   "churn_risk",          "VARCHAR"),
        ("",   "pipeline_updated_at", "TIMESTAMP"),
    ]
    m_x, m_y = 18.7, -1.8
    draw_table(ax, m_x, m_y, "mart_customer_rfm",
               MART, C["mart_header"], C["mart_row"], C["mart_row_alt"], col_w=DW)
    ax.text(m_x + DW/2, m_y - HEADER_H - len(MART)*ROW_H - 0.22,
            "Pre-aggregated  ·  Power BI connects here",
            ha="center", fontsize=7.5, color="#8E44AD", style="italic")

    # ── Connection lines ──
    def mid_right(tx, ty, cols, col_w=DW):
        return tx + col_w, ty - HEADER_H - len(cols)*ROW_H/2

    def mid_left(tx, ty, cols, col_w=DW):
        return tx, ty - HEADER_H - len(cols)*ROW_H/2

    def mid_bottom(tx, ty, cols, col_w=DW):
        return tx + col_w/2, ty - HEADER_H - len(cols)*ROW_H

    def mid_top(tx, ty, col_w=DW):
        return tx + col_w/2, ty

    GREEN = "#27AE60"
    ORANGE = "#E67E22"

    # fact_orders ↔ dim_customer
    ax.annotate("", xy=mid_right(dc_x, dc_y, DC),
                xytext=(fo_x, fo_y - HEADER_H - 2*ROW_H - ROW_H/2),
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1.8,
                                connectionstyle="arc3,rad=0.15"), zorder=5)

    # fact_orders ↔ dim_date
    ax.annotate("", xy=mid_bottom(dd_x, dd_y, DD),
                xytext=(fo_x + DW*0.35, fo_y),
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1.8), zorder=5)

    # fact_order_items ↔ dim_customer
    ax.annotate("", xy=(dc_x + DW, dc_y - HEADER_H - len(DC)*ROW_H*0.7),
                xytext=(fi_x, fi_y - HEADER_H - 3*ROW_H - ROW_H/2),
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1.8,
                                connectionstyle="arc3,rad=0.2"), zorder=5)

    # fact_order_items ↔ dim_product
    ax.annotate("", xy=(dp_x, dp_y - HEADER_H - len(DP)*ROW_H/2),
                xytext=(fi_x + DW, fi_y - HEADER_H - 4*ROW_H - ROW_H/2),
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1.8,
                                connectionstyle="arc3,rad=-0.15"), zorder=5)

    # fact_order_items ↔ dim_date
    ax.annotate("", xy=mid_bottom(dd_x, dd_y, DD),
                xytext=(fi_x + DW*0.6, fi_y),
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1.8,
                                connectionstyle="arc3,rad=0.1"), zorder=5)

    # fact_orders → mart (aggregated from)
    ax.annotate("", xy=(m_x, m_y - HEADER_H - 5*ROW_H),
                xytext=(fo_x + DW, fo_y - HEADER_H - 5*ROW_H),
                arrowprops=dict(arrowstyle="-|>", color=C["mart_header"],
                                lw=2.2, linestyle=(0, (5, 3))), zorder=5)
    ax.text((fo_x + DW + m_x)/2, fo_y - HEADER_H - 5*ROW_H + 0.15,
            "aggregated from", ha="center", fontsize=8,
            color=C["mart_header"], style="italic")

    # ── Legend ──
    legend_x, legend_y = 0.4, -12.3
    items = [
        (C["dim_header"],  "Dimension Table"),
        (C["fact_header"], "Fact Table"),
        (C["mart_header"], "Analytics Mart"),
        ("#2C3E50",        "FK Relationship"),
    ]
    for i, (col, lbl) in enumerate(items):
        bx = legend_x + i * 4.5
        rect = mpatches.Rectangle((bx, legend_y), 0.5, 0.28,
                                   facecolor=col, edgecolor="none")
        ax.add_patch(rect)
        ax.text(bx + 0.65, legend_y + 0.14, lbl,
                fontsize=9, va="center", color="#333333")

    plt.tight_layout(pad=0.5)
    out = OUT_DIR / "olap_star_schema.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print(f"  Saved: {out}")


if __name__ == "__main__":
    print("Generating diagram images...")
    build_oltp()
    build_olap()
    print()
    print("Done. Open the PNG files to view:")
    print("  architecture/diagrams/oltp_er_diagram.png")
    print("  architecture/diagrams/olap_star_schema.png")
