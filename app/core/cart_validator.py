from app.mcp.tools import kapruka_get_product, parse_product_detail


async def validate_cart(cart: list[dict]) -> dict:
    """
    Re-check each cart item against live Kapruka data before checkout.
    Prices can change, stock can run out — always validate before create_order.
    """
    issues = []
    validated_items = []

    for item in cart:
        try:
            result = await kapruka_get_product(product_id=item["product_id"])
            detail = parse_product_detail(result)

            # Stock check — parse_product_detail returns stock_detail string
            stock_detail = detail.get("stock_detail", "In stock")
            if "out of stock" in stock_detail.lower() or "unavailable" in stock_detail.lower():
                issues.append(f"'{item['name']}' is now out of stock")
                continue

            # Price drift check
            if detail.get("price") and abs(detail["price"] - item["price"]) > 1:
                issues.append(
                    f"'{item['name']}' price changed: LKR {item['price']:,.0f} → LKR {detail['price']:,.0f}"
                )
                item = {**item, "price": detail["price"]}  # use current price

            validated_items.append(item)

        except Exception as e:
            # If we can't verify an item, let it through with a soft warning
            issues.append(f"Could not verify '{item.get('name', item['product_id'])}' — proceeding anyway")
            validated_items.append(item)

    return {"items": validated_items, "issues": issues}
