from fastapi import Header, HTTPException
import os


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.environ.get("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")