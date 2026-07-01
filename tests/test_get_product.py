import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import asyncio
from app.mcp.tools import kapruka_get_product, kapruka_track_order

async def test():
    # Use a real product_id from your earlier search results
    result = await kapruka_track_order(order_number="VPAY827982BA")
    print(result)

asyncio.run(test())