"""Command-line entry point for the first local milestone."""

from pathlib import Path

from .analysis import load_sales, profit_by_month, profit_by_product, summarize_sales
from .charts import save_monthly_profit_chart


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    sales = load_sales(project_root / "data" / "sales.csv")
    summary = summarize_sales(sales)
    product_profits = profit_by_product(sales)
    monthly_profits = profit_by_month(sales)
    chart_path = save_monthly_profit_chart(
        monthly_profits, project_root / "outputs" / "monthly_profit.png"
    )

    print("销售数据分析结果")
    print(f"订单数：{summary['order_count']}")
    print(f"总销售额：{summary['total_revenue']:.2f}")
    print(f"总利润：{summary['total_profit']:.2f}")
    print(f"利润最高的产品：{summary['top_product_by_profit']}")
    print("\n各产品利润：")
    for product, profit in product_profits.items():
        print(f"- {product}: {profit:.2f}")

    print("\n各月利润：")
    for month, profit in monthly_profits.items():
        print(f"- {month}: {profit:.2f}")

    print(f"\n月度利润图表已保存：{chart_path}")


if __name__ == "__main__":
    main()
