import boto3
import httpx
from typing import Dict, Any
from agentcore_gateway_config import AgentCoreGatewayConfig, ToolTarget
from agentcore_identity import AgentCoreIdentity
from tenant_context import TenantContext

class AgentCoreGateway:
    def __init__(self, config: AgentCoreGatewayConfig):
        self.config = config
        self.identity = AgentCoreIdentity()
        self.lambda_client = boto3.client('lambda')
    
    async def invoke_tool(self, context: TenantContext, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """MCPツール呼び出しを適切なターゲットに変換"""
        tool_config = self.config.get_tool_config(tool_name)
        if not tool_config:
            raise ValueError(f"Tool {tool_name} not found")
        
        # テナントのアクセス権限をチェック
        if not self.identity.validate_tenant_access(context, tool_name):
            raise PermissionError(f"Tenant {context.tenant_id} cannot access {tool_name}")
        
        if tool_config.type == "lambda":
            return await self._invoke_lambda(context, tool_config, payload)
        elif tool_config.type == "rest_api":
            return await self._invoke_rest_api(context, tool_config, payload)
        else:
            raise ValueError(f"Unsupported tool type: {tool_config.type}")
    
    async def _invoke_lambda(self, context: TenantContext, tool_config: ToolTarget, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Lambda関数の呼び出し（テナントスコープ付きIAM）"""
        # テナント固有のロールを取得
        tenant_role_mapping = tool_config.auth_config["tenant_role_mapping"]
        role_arn = tenant_role_mapping.get(context.tenant_id)
        if not role_arn:
            raise PermissionError(f"No role configured for tenant {context.tenant_id}")
        
        # テナントスコープ付きの認証情報を取得
        credentials = self.identity.get_tenant_scoped_credentials(context, role_arn)
        
        # テナント固有のLambdaクライアントを作成
        tenant_lambda = boto3.client(
            'lambda',
            aws_access_key_id=credentials['aws_access_key_id'],
            aws_secret_access_key=credentials['aws_secret_access_key'],
            aws_session_token=credentials['aws_session_token']
        )
        
        # Lambda関数を呼び出し
        response = tenant_lambda.invoke(
            FunctionName=tool_config.endpoint,
            Payload=str(payload).encode()
        )
        
        return {"result": response['Payload'].read().decode()}
    
    async def _invoke_rest_api(self, context: TenantContext, tool_config: ToolTarget, payload: Dict[str, Any]) -> Dict[str, Any]:
        """REST API呼び出し（テナントスコープ付きOAuth）"""
        oauth_config = tool_config.auth_config["oauth_config"]
        service = oauth_config.get("service")
        
        # テナント固有のOAuthトークンを取得
        token = self.identity.get_oauth_token(context, service)
        if not token:
            raise PermissionError(f"No OAuth token for tenant {context.tenant_id}")
        
        # API呼び出し
        async with httpx.AsyncClient() as client:
            response = await client.post(
                tool_config.endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": context.tenant_id
                }
            )
        
        return response.json()
