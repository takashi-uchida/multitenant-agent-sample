from typing import Dict, Any
from tenant.tenant_context import TenantContext
from .agentcore_gateway import AgentCoreGateway
from .agentcore_gateway_config import AgentCoreGatewayConfig
from tenant.tenant_aware_agent import TenantAwareAgent, AgentConfig

class AgentCoreIntegratedAgent(TenantAwareAgent):
    def __init__(self, gateway_config: AgentCoreGatewayConfig):
        super().__init__()
        self.gateway = AgentCoreGateway(gateway_config)
    
    async def invoke_with_tools(self, context: TenantContext, agent_name: str, message: str, tools_needed: list[str] = None) -> str:
        """ツール呼び出しを含むエージェント実行"""
        config = self.get_agent_config(context, agent_name)
        
        # ツールが必要な場合は実行
        tool_results = {}
        if tools_needed:
            for tool_name in tools_needed:
                if tool_name in config.tools:
                    try:
                        result = await self.gateway.invoke_tool(
                            context, 
                            tool_name, 
                            {"query": message}
                        )
                        tool_results[tool_name] = result
                    except Exception as e:
                        tool_results[tool_name] = {"error": str(e)}
        
        # プロンプトにツール結果を含める
        enhanced_prompt = config.prompt_template.format(
            tenant_id=context.tenant_id,
            user_message=message,
            tool_results=tool_results
        )
        
        return f"Response from {config.model} for tenant {context.tenant_id} with tools: {list(tool_results.keys())}"
