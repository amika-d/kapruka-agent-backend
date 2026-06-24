import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import asyncio
from app.mcp.tools import kapruka_get_product

async def test():
    # Use a real product_id from your earlier search results
    result = await kapruka_get_product(product_id="EF_PC_PERF0V1385P00055")
    print(result)

asyncio.run(test())