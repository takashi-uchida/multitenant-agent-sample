from fastapi import FastAPI, HTTPException, Header
import httpx
from tenant_context import TenantContextManager

app = FastAPI()

class MCPProxy:
    def __init__(self, product_server_url: str):
        self.product_server_url = product_server_url
        self.session_store = {}  # session_id -> TenantContext
    
    def register_session(self, session_id: str, context):
        self.session_store[session_id] = context

@app.post("/mcp/tools/{tool_name}")
async def proxy_tool_call(
    tool_name: str,
    payload: dict,
    session_id: str = Header(...)
):
    proxy = MCPProxy("http://product-server:8080")
    
    # セッションからテナントコンテキストを取得
    context = proxy.session_store.get(session_id)
    if not context:
        raise HTTPException(401, "Invalid session")
    
    # プロダクトサーバーのRPCに変換して呼び出し
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{proxy.product_server_url}/rpc/{tool_name}",
            json=payload,
            headers={
                "X-Tenant-ID": context.tenant_id,
                "X-User-ID": context.user_id
            }
        )
    
    return response.json()
