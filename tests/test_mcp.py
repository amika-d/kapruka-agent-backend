# test_mcp.py in project root
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import asyncio
# from app.mcp.tools import kapruka_search_products

from app.mcp.tools import kapruka_list_categories
async def test():
    result = await kapruka_list_categories(
        depth=2

    )
    print(result)

asyncio.run(test())