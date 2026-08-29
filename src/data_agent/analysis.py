"""Deterministic data tools that a future agent can call."""

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "order_id",
    "date",
    "region",
    "product",
    "quantity",
    "unit_price",
    "unit_cost",
    "refund_amount",
}


def load_sales(path: str | Path) -> pd.DataFrame:
    """Load sales data, validate its schema, and add calculated columns."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到数据文件：{csv_path}")

    frame = pd.read_csv(csv_path)
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"数据缺少必需字段：{missing}")

    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["revenue"] = frame["quantity"] * frame["unit_price"]
    frame["cost"] = frame["quantity"] * frame["unit_cost"]
    frame["profit"] = frame["revenue"] - frame["cost"] - frame["refund_amount"]
    return frame


def summarize_sales(frame: pd.DataFrame) -> dict[str, int | float | str]:
    """Return a small, machine-readable sales summary."""
    if frame.empty:
        raise ValueError("数据为空，无法生成汇总。")

    product_profit = frame.groupby("product")["profit"].sum()
    total_revenue = float(frame["revenue"].sum())
    total_profit = float(frame["profit"].sum())
    return {
        "order_count": int(len(frame)),
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "profit_margin": total_profit / total_revenue * 100 if total_revenue else 0.0,
        "total_refunds": float(frame["refund_amount"].sum()),
        "average_order_value": total_revenue / len(frame),
        "top_product_by_profit": str(product_profit.idxmax()),
    }


def profit_by_product(frame: pd.DataFrame) -> dict[str, float]:
    """Calculate total profit for each product."""
    product_profit = frame.groupby("product")["profit"].sum()
    return {product: float(profit) for product, profit in product_profit.items()}


def profit_by_month(frame: pd.DataFrame) -> dict[str, float]:
    """Calculate total profit for each calendar month."""
    monthly_frame = frame.copy()
    monthly_frame["month"] = monthly_frame["date"].dt.strftime("%Y-%m")
    monthly_profit = monthly_frame.groupby("month")["profit"].sum()
    return {month: float(profit) for month, profit in monthly_profit.items()}
