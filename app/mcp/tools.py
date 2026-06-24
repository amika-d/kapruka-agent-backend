from typing import Dict, Any, Optional, List
import re
from app.mcp.client import get_client

def parse_search_results(raw: dict) -> list[dict]:
    text = raw.get("result", "")
    products = []
    
    # Split by numbered items
    blocks = re.split(r'\n\*\*\d+\.', text)
    
    for block in blocks[1:]:  # skip header
        product = {}
        
        # Name
        name_match = re.match(r'\s*(.+?)\*\*', block)
        if name_match:
            product["name"] = name_match.group(1).strip()
        
        # ID
        id_match = re.search(r'ID:\s*`([^`]+)`', block)
        if id_match:
            product["product_id"] = id_match.group(1)
        
        # Price
        price_match = re.search(r'LKR\s*([\d,]+)', block)
        if price_match:
            product["price"] = float(price_match.group(1).replace(",", ""))
            product["currency"] = "LKR"
        
        # Stock
        product["in_stock"] = "In stock" in block or "in stock" in block
        
        # URL
        url_match = re.search(r'\[View product\]\(([^)]+)\)', block)
        if url_match:
            product["url"] = url_match.group(1)
        
        # image_url — not in search results, need get_product call
        product["image_url"] = ""
        
        if product.get("product_id"):
            products.append(product)
    
    return products

def parse_product_detail(raw: dict) -> dict:
    text = raw.get("result", "")
    product = {}

    img_match = re.search(r'\*\*Image\*\*:\s*(https?://\S+)', text)
    if not img_match:
        img_match = re.search(r'!\[.*?\]\((https?://[^)]+)\)', text)
    if img_match:
        product["image_url"] = img_match.group(1)

    stock_match = re.search(r'\*\*Stock\*\*:\s*(.+)', text)
    if stock_match:
        product["stock_detail"] = stock_match.group(1).strip()

    vendor_match = re.search(r'\*\*Vendor\*\*:\s*(.+)', text)
    if vendor_match:
        product["vendor"] = vendor_match.group(1).strip()

    orig_match = re.search(r'~~LKR\s*([\d,]+)~~', text)
    if orig_match:
        product["original_price"] = float(orig_match.group(1).replace(",", ""))

    return product

async def kapruka_search_products(
    q: str,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = True,
    sort: str = "relevance",
    limit: int = 5,
    cursor: Optional[str] = None,
    currency: str = "LKR"
) -> dict:
    args = {"params": {
        "q": q, "category": category, "min_price": min_price,
        "max_price": max_price, "in_stock_only": in_stock_only,
        "sort": sort, "limit": limit, "cursor": cursor, "currency": currency
    }}
    # clean_args = {k: v for k, v in args.items() if v is not None}
    args["params"] = {k: v for k, v in args["params"].items() if v is not None}
    client = await get_client()
    return await client.call_tool("kapruka_search_products", args)

async def kapruka_get_product(product_id: str, currency: str = "LKR") -> dict:
    args = {"params": {"product_id": product_id, "currency": currency}}
    args["params"] = {k: v for k, v in args["params"].items() if v is not None}
    client = await get_client()
    return await client.call_tool("kapruka_get_product", args)

async def kapruka_list_categories(depth: int = 1) -> dict:
    args = {"params": {"depth": depth}}
    args["params"] = {k: v for k, v in args["params"].items() if v is not None}
    client = await get_client()
    return await client.call_tool("kapruka_list_categories", args)

async def kapruka_list_delivery_cities(query: str, limit: int = 10) -> dict:
    args = {"params": {"query": query, "limit": limit}}
    args["params"] = {k: v for k, v in args["params"].items() if v is not None}
    client = await get_client()
    return await client.call_tool("kapruka_list_delivery_cities", args)

async def kapruka_check_delivery(city: str, delivery_date: str, product_id: Optional[str] = None) -> dict:
    args = {"params": {"city": city, "delivery_date": delivery_date, "product_id": product_id}}
    args["params"] = {k: v for k, v in args["params"].items() if v is not None}
    client = await get_client()
    return await client.call_tool("kapruka_check_delivery", args)

async def kapruka_create_order(
    cart: List[dict],
    recipient: dict,
    delivery: dict,
    sender: dict,
    gift_message: Optional[str] = None,
    currency: str = "LKR"
) -> dict:
    args = {"params": {
        "cart": cart, "recipient": recipient, "delivery": delivery,
        "sender": sender, "gift_message": gift_message, "currency": currency
    }}
    args["params"] = {k: v for k, v in args["params"].items() if v is not None}
    client = await get_client()
    return await client.call_tool("kapruka_create_order", args)

async def kapruka_track_order(order_number: str) -> dict:
    args = {"params": {"order_number": order_number}}
    args["params"] = {k: v for k, v in args["params"].items() if v is not None}
    client = await get_client()
    return await client.call_tool("kapruka_track_order", args)

async def get_complementary_products(primary_category: str, occasion: Optional[str] = None) -> dict:
    suggestions = []
    
    if "cake" in primary_category.lower():
        if occasion and "anniversary" in occasion.lower():
            res1 = await kapruka_search_products(q="roses bouquet", limit=2)
            res2 = await kapruka_search_products(q="greeting card anniversary", limit=2)
            suggestions.extend(res1.get("products", []))
            suggestions.extend(res2.get("products", []))
        elif occasion and "birthday" in occasion.lower():
            res1 = await kapruka_search_products(q="balloons", limit=2)
            res2 = await kapruka_search_products(q="birthday card", limit=2)
            suggestions.extend(res1.get("products", []))
            suggestions.extend(res2.get("products", []))
    elif "electronics" in primary_category.lower():
        res1 = await kapruka_search_products(q="accessories " + primary_category, limit=3)
        suggestions.extend(res1.get("products", []))
        
    if not suggestions:
        res = await kapruka_search_products(q="gift box", limit=2)
        suggestions.extend(res.get("products", []))
        
    return {"suggestions": suggestions}

import re 
def parse_search_results(raw: dict) -> list[dict]:
    text = raw.get("result", "")
    products = []
    
    # Split by numbered items
    blocks = re.split(r'\n\*\*\d+\.', text)
    
    for block in blocks[1:]:  # skip header
        product = {}
        
        # Name
        name_match = re.match(r'\s*(.+?)\*\*', block)
        if name_match:
            product["name"] = name_match.group(1).strip()
        
        # ID
        id_match = re.search(r'ID:\s*`([^`]+)`', block)
        if id_match:
            product["product_id"] = id_match.group(1)
        
        # Price
        price_match = re.search(r'LKR\s*([\d,]+)', block)
        if price_match:
            product["price"] = float(price_match.group(1).replace(",", ""))
            product["currency"] = "LKR"
        
        # Stock
        product["in_stock"] = "In stock" in block or "in stock" in block
        
        # URL
        url_match = re.search(r'\[View product\]\(([^)]+)\)', block)
        if url_match:
            product["url"] = url_match.group(1)
        
        # image_url — not in search results, need get_product call
        product["image_url"] = ""
        
        if product.get("product_id"):
            products.append(product)
    
    return products


TOOL_EXECUTOR = {
    "kapruka_search_products": kapruka_search_products,
    "kapruka_get_product": kapruka_get_product,
    "kapruka_list_categories": kapruka_list_categories,
    "kapruka_list_delivery_cities": kapruka_list_delivery_cities,
    "kapruka_check_delivery": kapruka_check_delivery,
    "kapruka_create_order": kapruka_create_order,
    "kapruka_track_order": kapruka_track_order
}

KAPRUKA_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "kapruka_search_products",
            "description": "Search the Kapruka catalog for products based on a text query, category, price bounds, and stock availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "The main search query text (e.g., 'cake', 'saree')."},
                    "category": {"type": "string", "description": "Optional category name to filter by (e.g., 'Fashion', 'Grocery')."},
                    "min_price": {"type": "number", "description": "Minimum price boundary in the specified currency."},
                    "max_price": {"type": "number", "description": "Maximum price boundary in the specified currency."},
                    "in_stock_only": {"type": "boolean", "description": "Set to true to only return products currently in stock."},
                    "sort": {"type": "string", "description": "Sorting order, e.g., 'relevance', 'price_asc', 'price_desc'."},
                    "limit": {"type": "integer", "description": "Maximum number of results to return (default 5)."},
                    "cursor": {"type": "string", "description": "Pagination cursor string for fetching the next page."},
                    "currency": {"type": "string", "description": "Currency code for prices (default 'LKR')."}
                },
                "required": ["q"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kapruka_get_product",
            "description": "Retrieve rich details for a specific product using its ID, including variant details and exact stock status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "The unique Kapruka product identifier."},
                    "currency": {"type": "string", "description": "Currency code for prices (default 'LKR')."}
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kapruka_list_categories",
            "description": "Get a list of available product categories on Kapruka up to a certain depth.",
            "parameters": {
                "type": "object",
                "properties": {
                    "depth": {"type": "integer", "description": "Category tree depth to fetch (default 1)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kapruka_list_delivery_cities",
            "description": "Search for valid delivery cities in Sri Lanka to ensure a location is supported before checkout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Partial or full city name to search for (e.g., 'Col', 'Kandy')."},
                    "limit": {"type": "integer", "description": "Maximum number of city results to return (default 10)."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kapruka_check_delivery",
            "description": "Check if delivery is available for a specific city on a specific date, and retrieve the delivery price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "The valid delivery city name."},
                    "delivery_date": {"type": "string", "description": "The requested delivery date in YYYY-MM-DD format."},
                    "product_id": {"type": "string", "description": "Optional specific product ID to check perishable constraints against."}
                },
                "required": ["city", "delivery_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kapruka_create_order",
            "description": "Initialize a new order checkout session and receive a payment URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cart": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of cart item objects containing product_id and quantity."
                    },
                    "recipient": {
                        "type": "object",
                        "description": "Recipient details object with name and phone."
                    },
                    "delivery": {
                        "type": "object",
                        "description": "Delivery details object with city and date."
                    },
                    "sender": {
                        "type": "object",
                        "description": "Sender details object with name and email."
                    },
                    "gift_message": {"type": "string", "description": "Optional personalized message to include with the order."},
                    "currency": {"type": "string", "description": "Currency for checkout (default 'LKR')."}
                },
                "required": ["cart", "recipient", "delivery", "sender"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kapruka_track_order",
            "description": "Track the current status and historical timeline of an existing Kapruka order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_number": {"type": "string", "description": "The Kapruka order reference number."}
                },
                "required": ["order_number"]
            }
        }
    }
]
