from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ToolTarget:
    type: str  # "lambda" | "rest_api"
    endpoint: str
    auth_config: Dict[str, Any]

class AgentCoreGatewayConfig:
    def __init__(self):
        self.tools = {}
    
    def register_lambda_tool(self, tool_name: str, function_arn: str, tenant_role_mapping: Dict[str, str]):
        """Lambda関数をツールとして登録"""
        self.tools[tool_name] = ToolTarget(
            type="lambda",
            endpoint=function_arn,
            auth_config={
                "type": "iam_role",
                "tenant_role_mapping": tenant_role_mapping  # tenant_id -> role_arn
            }
        )
    
    def register_api_tool(self, tool_name: str, api_endpoint: str, oauth_config: Dict[str, str]):
        """REST APIをツールとして登録"""
        self.tools[tool_name] = ToolTarget(
            type="rest_api", 
            endpoint=api_endpoint,
            auth_config={
                "type": "oauth2",
                "oauth_config": oauth_config
            }
        )
    
    def get_tool_config(self, tool_name: str) -> ToolTarget:
        return self.tools.get(tool_name)
