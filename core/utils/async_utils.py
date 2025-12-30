import asyncio
from typing import List, Any, Coroutine

async def batch_query(tasks: List[Coroutine]) -> List[Any]:
    """
    Executes multiple async tasks concurrently and returns their results.
    Simplified wrapper for asyncio.gather.
    """
    if not tasks:
        return []
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Filter out exceptions if needed or log them
        # For now, we return the raw list which might include Exception objects
        return results
    except Exception as e:
        # This catch is mainly for setup errors in gather itself
        return [e] * len(tasks)
