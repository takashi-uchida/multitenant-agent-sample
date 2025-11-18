# マルチテナントSaaS AIエージェント実装ガイド

## 概要

このガイドでは、Amazon Bedrock AgentCoreを使用してマルチテナントSaaSでAIエージェントを実装する方法を説明します。Amazon Bedrock AgentCoreのサンプルリポジトリから抽出した重要な実装パターンとベストプラクティスを基に、実用的な実装手順を提供します。

## 1. アーキテクチャ概要

### 1.1 マルチテナント対応の核心コンポーネント

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Tenant A      │    │   Tenant B      │    │   Tenant C      │
│   Users         │    │   Users         │    │   Users         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │        AgentCore Identity (認証・認可)           │
         └─────────────────────────────────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │        AgentCore Gateway (API管理)              │
         └─────────────────────────────────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │        AgentCore Runtime (エージェント実行)      │
         └─────────────────────────────────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │        AgentCore Memory (テナント別メモリ)       │
         └─────────────────────────────────────────────────┘
```

## 2. 必須コンポーネントの実装

### 2.1 AgentCore Identity - マルチテナント認証

#### 基本設定

```python
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload, context):
    # テナント情報の取得
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id") 
    actor_id = payload.get("actor_id")
    
    # セッション管理（テナント別）
    session_id = f"{tenant_id}_{context.session_id}"
    
    # テナント固有の処理
    return await process_tenant_request(tenant_id, user_id, payload)
```

#### Cognito認証プロバイダーの設定

```python
# scripts/cognito_credentials_provider.py の実装例
import boto3
from bedrock_agentcore_identity import CredentialsProvider

def create_cognito_provider(name: str, tenant_id: str):
    """テナント別Cognito認証プロバイダーを作成"""
    
    # テナント固有のCognito設定
    cognito_config = {
        "user_pool_id": f"tenant-{tenant_id}-pool",
        "client_id": f"tenant-{tenant_id}-client",
        "domain": f"tenant-{tenant_id}.auth.region.amazoncognito.com"
    }
    
    provider = CredentialsProvider.create(
        name=f"{name}-{tenant_id}",
        provider_type="cognito",
        config=cognito_config
    )
    
    return provider
```

### 2.2 AgentCore Gateway - API管理とルーティング

#### テナント別APIエンドポイント設定

```python
# scripts/agentcore_gateway.py の実装例
from bedrock_agentcore_gateway import Gateway

def create_tenant_gateway(tenant_id: str):
    """テナント固有のゲートウェイを作成"""
    
    gateway_config = {
        "name": f"tenant-{tenant_id}-gateway",
        "endpoints": [
            {
                "path": f"/api/v1/tenant/{tenant_id}/agent",
                "method": "POST",
                "target": f"tenant-{tenant_id}-agent",
                "auth_required": True,
                "tenant_isolation": True
            }
        ],
        "rate_limiting": {
            "requests_per_minute": 100,
            "burst_limit": 20
        }
    }
    
    return Gateway.create(gateway_config)
```

### 2.3 AgentCore Memory - テナント分離メモリ

#### テナント別メモリストア実装

```python
# scripts/agentcore_memory.py の実装例
from bedrock_agentcore_memory import Memory

class TenantMemoryManager:
    def __init__(self):
        self.memories = {}
    
    def get_tenant_memory(self, tenant_id: str):
        """テナント固有のメモリインスタンスを取得"""
        if tenant_id not in self.memories:
            self.memories[tenant_id] = Memory.create(
                name=f"tenant-{tenant_id}-memory",
                isolation_level="tenant",
                encryption_key=f"tenant-{tenant_id}-key"
            )
        return self.memories[tenant_id]
    
    async def store_conversation(self, tenant_id: str, session_id: str, message: dict):
        """テナント別会話履歴の保存"""
        memory = self.get_tenant_memory(tenant_id)
        await memory.store(
            session_id=f"{tenant_id}_{session_id}",
            data=message,
            metadata={"tenant_id": tenant_id}
        )
```

## 3. エージェント実装パターン

### 3.1 メインエージェントクラス

```python
# main.py の実装例
from agent_config.context import TenantContext
from agent_config.access_token import get_tenant_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import asyncio
import logging

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload, context):
    # テナント情報の抽出
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    user_message = payload["prompt"]
    
    # テナント固有のコンテキスト設定
    if not TenantContext.get_tenant_ctx():
        TenantContext.set_tenant_ctx(tenant_id)
    
    # テナント固有のアクセストークン取得
    if not TenantContext.get_access_token_ctx():
        token = await get_tenant_access_token(tenant_id)
        TenantContext.set_access_token_ctx(token)
    
    # セッション管理
    session_id = f"{tenant_id}_{context.session_id}"
    
    # エージェントタスクの実行
    task = asyncio.create_task(
        tenant_agent_task(
            tenant_id=tenant_id,
            user_id=user_id,
            user_message=user_message,
            session_id=session_id
        )
    )
    
    # ストリーミングレスポンス
    async def stream_output():
        async for item in task:
            yield item
    
    return stream_output()
```

### 3.2 テナント固有エージェントタスク

```python
# agent_config/agent_task.py の実装例
from strands import Agent
from .tools import get_tenant_tools
from .memory import get_tenant_memory

async def tenant_agent_task(tenant_id: str, user_id: str, user_message: str, session_id: str):
    """テナント固有のエージェントタスクを実行"""
    
    # テナント固有の設定を取得
    tenant_config = await get_tenant_config(tenant_id)
    
    # テナント固有のツールを取得
    tools = await get_tenant_tools(tenant_id)
    
    # テナント固有のメモリを取得
    memory = await get_tenant_memory(tenant_id, session_id)
    
    # エージェントの初期化
    agent = Agent(
        model=tenant_config.get("model", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
        tools=tools,
        memory=memory,
        system_prompt=tenant_config.get("system_prompt", "You are a helpful assistant.")
    )
    
    # 会話履歴の取得
    conversation_history = await memory.get_conversation_history(session_id)
    
    # エージェントの実行
    result = await agent.run(
        message=user_message,
        context={
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "history": conversation_history
        }
    )
    
    # 結果の保存
    await memory.store_conversation(session_id, {
        "user_message": user_message,
        "agent_response": result.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return result
```

## 4. テナント分離の実装

### 4.1 データ分離

```python
# テナント別データベース接続
class TenantDatabaseManager:
    def __init__(self):
        self.connections = {}
    
    def get_tenant_connection(self, tenant_id: str):
        """テナント固有のデータベース接続を取得"""
        if tenant_id not in self.connections:
            self.connections[tenant_id] = create_tenant_database(tenant_id)
        return self.connections[tenant_id]

# テナント別S3バケット
class TenantStorageManager:
    def get_tenant_bucket(self, tenant_id: str):
        """テナント固有のS3バケットを取得"""
        return f"tenant-{tenant_id}-data-bucket"
    
    async def store_tenant_file(self, tenant_id: str, file_key: str, content: bytes):
        """テナント固有のファイル保存"""
        bucket = self.get_tenant_bucket(tenant_id)
        s3_client = boto3.client('s3')
        await s3_client.put_object(
            Bucket=bucket,
            Key=file_key,
            Body=content,
            ServerSideEncryption='AES256'
        )
```

### 4.2 設定管理

```python
# テナント別設定管理
class TenantConfigManager:
    def __init__(self):
        self.ssm_client = boto3.client('ssm')
    
    async def get_tenant_config(self, tenant_id: str):
        """テナント固有の設定を取得"""
        try:
            response = self.ssm_client.get_parameters_by_path(
                Path=f'/app/tenant/{tenant_id}/',
                Recursive=True,
                WithDecryption=True
            )
            
            config = {}
            for param in response['Parameters']:
                key = param['Name'].split('/')[-1]
                config[key] = param['Value']
            
            return config
        except Exception as e:
            logger.error(f"Failed to get tenant config for {tenant_id}: {e}")
            return {}
    
    async def set_tenant_config(self, tenant_id: str, key: str, value: str):
        """テナント固有の設定を保存"""
        self.ssm_client.put_parameter(
            Name=f'/app/tenant/{tenant_id}/{key}',
            Value=value,
            Type='SecureString',
            Overwrite=True
        )
```

## 5. セキュリティ実装

### 5.1 テナント認証・認可

```python
# テナント認証ミドルウェア
class TenantAuthMiddleware:
    def __init__(self):
        self.identity_client = boto3.client('bedrock-agentcore-identity')
    
    async def authenticate_tenant_user(self, token: str, tenant_id: str):
        """テナントユーザーの認証"""
        try:
            # トークンの検証
            response = self.identity_client.validate_token(
                token=token,
                tenant_id=tenant_id
            )
            
            if response['valid']:
                return {
                    'user_id': response['user_id'],
                    'tenant_id': response['tenant_id'],
                    'permissions': response['permissions']
                }
            else:
                raise UnauthorizedError("Invalid token")
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise UnauthorizedError("Authentication failed")
    
    async def authorize_tenant_action(self, user_context: dict, action: str, resource: str):
        """テナント内でのアクション認可"""
        permissions = user_context.get('permissions', [])
        
        # リソースレベルの認可チェック
        if f"{action}:{resource}" not in permissions:
            raise ForbiddenError(f"Insufficient permissions for {action} on {resource}")
        
        return True
```

### 5.2 データ暗号化

```python
# テナント別暗号化
class TenantEncryption:
    def __init__(self):
        self.kms_client = boto3.client('kms')
    
    def get_tenant_key(self, tenant_id: str):
        """テナント固有の暗号化キーを取得"""
        return f"alias/tenant-{tenant_id}-key"
    
    async def encrypt_tenant_data(self, tenant_id: str, data: str):
        """テナントデータの暗号化"""
        key_id = self.get_tenant_key(tenant_id)
        
        response = self.kms_client.encrypt(
            KeyId=key_id,
            Plaintext=data.encode('utf-8')
        )
        
        return response['CiphertextBlob']
    
    async def decrypt_tenant_data(self, tenant_id: str, encrypted_data: bytes):
        """テナントデータの復号化"""
        response = self.kms_client.decrypt(
            CiphertextBlob=encrypted_data
        )
        
        return response['Plaintext'].decode('utf-8')
```

## 6. デプロイメント設定

### 6.1 Infrastructure as Code

```yaml
# cloudformation/tenant-infrastructure.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Multi-tenant AI Agent Infrastructure'

Parameters:
  TenantId:
    Type: String
    Description: 'Unique tenant identifier'
  
Resources:
  # テナント固有のCognito User Pool
  TenantUserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub 'tenant-${TenantId}-pool'
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireUppercase: true
          RequireLowercase: true
          RequireNumbers: true
          RequireSymbols: true
  
  # テナント固有のS3バケット
  TenantDataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub 'tenant-${TenantId}-data-bucket'
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
  
  # テナント固有のKMSキー
  TenantKMSKey:
    Type: AWS::KMS::Key
    Properties:
      Description: !Sub 'Encryption key for tenant ${TenantId}'
      KeyPolicy:
        Statement:
          - Sid: Enable IAM User Permissions
            Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${AWS::AccountId}:root'
            Action: 'kms:*'
            Resource: '*'
```

### 6.2 デプロイメントスクリプト

```bash
#!/bin/bash
# scripts/deploy-tenant.sh

TENANT_ID=$1
AWS_REGION=${AWS_DEFAULT_REGION:-us-east-1}

if [ -z "$TENANT_ID" ]; then
    echo "Usage: $0 <tenant-id>"
    exit 1
fi

echo "Deploying infrastructure for tenant: $TENANT_ID"

# 1. テナント固有のインフラストラクチャをデプロイ
aws cloudformation deploy \
    --template-file cloudformation/tenant-infrastructure.yaml \
    --stack-name "tenant-$TENANT_ID-infrastructure" \
    --parameter-overrides TenantId=$TENANT_ID \
    --capabilities CAPABILITY_IAM \
    --region $AWS_REGION

# 2. AgentCore Gatewayを作成
python scripts/agentcore_gateway.py create --name "tenant-$TENANT_ID-gateway"

# 3. AgentCore Memoryを作成
python scripts/agentcore_memory.py create --name "tenant-$TENANT_ID-memory"

# 4. Cognito認証プロバイダーを作成
python scripts/cognito_credentials_provider.py create --name "tenant-$TENANT_ID-auth"

# 5. エージェントランタイムを設定
agentcore configure \
    --entrypoint main.py \
    --name "tenant-$TENANT_ID-agent" \
    --environment "TENANT_ID=$TENANT_ID"

# 6. エージェントをデプロイ
agentcore launch

echo "Deployment completed for tenant: $TENANT_ID"
```

## 7. 監視とログ

### 7.1 テナント別監視

```python
# monitoring/tenant_metrics.py
import boto3
from datetime import datetime, timedelta

class TenantMetrics:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
    
    async def record_tenant_metric(self, tenant_id: str, metric_name: str, value: float):
        """テナント固有のメトリクスを記録"""
        self.cloudwatch.put_metric_data(
            Namespace='MultiTenantAgent',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Dimensions': [
                        {
                            'Name': 'TenantId',
                            'Value': tenant_id
                        }
                    ],
                    'Value': value,
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
    
    async def get_tenant_usage(self, tenant_id: str, start_time: datetime, end_time: datetime):
        """テナントの使用状況を取得"""
        response = self.cloudwatch.get_metric_statistics(
            Namespace='MultiTenantAgent',
            MetricName='RequestCount',
            Dimensions=[
                {
                    'Name': 'TenantId',
                    'Value': tenant_id
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Sum']
        )
        
        return response['Datapoints']
```

## 8. テスト戦略

### 8.1 テナント分離テスト

```python
# test/test_tenant_isolation.py
import pytest
import asyncio
from main import invoke

class TestTenantIsolation:
    
    @pytest.mark.asyncio
    async def test_tenant_data_isolation(self):
        """テナント間のデータ分離をテスト"""
        
        # テナントAのデータ
        payload_a = {
            "tenant_id": "tenant-a",
            "user_id": "user-1",
            "prompt": "Store my preference: color=blue"
        }
        
        # テナントBのデータ
        payload_b = {
            "tenant_id": "tenant-b", 
            "user_id": "user-1",
            "prompt": "What is my color preference?"
        }
        
        # テナントAにデータを保存
        context_a = MockContext(session_id="session-1")
        await invoke(payload_a, context_a)
        
        # テナントBからデータを取得（アクセスできないことを確認）
        context_b = MockContext(session_id="session-2")
        result = await invoke(payload_b, context_b)
        
        # テナントBはテナントAのデータにアクセスできない
        assert "blue" not in str(result)
    
    @pytest.mark.asyncio
    async def test_tenant_authentication(self):
        """テナント認証をテスト"""
        
        # 無効なテナントIDでのアクセス
        payload = {
            "tenant_id": "invalid-tenant",
            "user_id": "user-1", 
            "prompt": "Hello"
        }
        
        context = MockContext(session_id="session-1")
        
        with pytest.raises(UnauthorizedError):
            await invoke(payload, context)
```

## 9. 運用ベストプラクティス

### 9.1 テナント管理

```python
# tenant_management/tenant_manager.py
class TenantManager:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.tenant_table = self.dynamodb.Table('tenant-registry')
    
    async def create_tenant(self, tenant_id: str, config: dict):
        """新しいテナントを作成"""
        
        # テナント情報をレジストリに登録
        self.tenant_table.put_item(
            Item={
                'tenant_id': tenant_id,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'active',
                'config': config
            }
        )
        
        # インフラストラクチャをデプロイ
        await self.deploy_tenant_infrastructure(tenant_id)
        
        # AgentCoreコンポーネントを設定
        await self.setup_agentcore_components(tenant_id, config)
    
    async def delete_tenant(self, tenant_id: str):
        """テナントを削除"""
        
        # データのバックアップ
        await self.backup_tenant_data(tenant_id)
        
        # AgentCoreコンポーネントを削除
        await self.cleanup_agentcore_components(tenant_id)
        
        # インフラストラクチャを削除
        await self.cleanup_tenant_infrastructure(tenant_id)
        
        # レジストリから削除
        self.tenant_table.delete_item(
            Key={'tenant_id': tenant_id}
        )
```

### 9.2 スケーリング戦略

```python
# scaling/auto_scaler.py
class TenantAutoScaler:
    def __init__(self):
        self.application_autoscaling = boto3.client('application-autoscaling')
    
    async def setup_tenant_scaling(self, tenant_id: str):
        """テナント固有のオートスケーリングを設定"""
        
        # スケーラブルターゲットを登録
        self.application_autoscaling.register_scalable_target(
            ServiceNamespace='bedrock-agentcore',
            ResourceId=f'tenant/{tenant_id}/agent',
            ScalableDimension='agentcore:agent:ProvisionedConcurrency',
            MinCapacity=1,
            MaxCapacity=100
        )
        
        # スケーリングポリシーを作成
        self.application_autoscaling.put_scaling_policy(
            PolicyName=f'tenant-{tenant_id}-scaling-policy',
            ServiceNamespace='bedrock-agentcore',
            ResourceId=f'tenant/{tenant_id}/agent',
            ScalableDimension='agentcore:agent:ProvisionedConcurrency',
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': 70.0,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'BedrockAgentCoreUtilization'
                }
            }
        )
```

## 10. まとめ

このガイドでは、Amazon Bedrock AgentCoreを使用したマルチテナントSaaS AIエージェントの実装について説明しました。

### 重要なポイント：

1. **テナント分離**: データ、設定、認証を完全に分離
2. **セキュリティ**: テナント別の暗号化と認証・認可
3. **スケーラビリティ**: テナント別のリソース管理とオートスケーリング
4. **運用性**: 監視、ログ、テナント管理の自動化
5. **テスト**: テナント分離の徹底的なテスト

### 次のステップ：

1. 本ガイドの実装パターンを参考に、具体的な要件に合わせてカスタマイズ
2. セキュリティ要件に応じた追加の保護機能の実装
3. 運用監視とアラートの設定
4. パフォーマンステストとキャパシティプランニング
5. 災害復旧とバックアップ戦略の策定

このガイドを基に、安全で拡張可能なマルチテナントAIエージェントシステムを構築してください。
