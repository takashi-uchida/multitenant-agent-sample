import boto3
from botocore.exceptions import ClientError

class TenantIsolatedStorage:
    def __init__(self, table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    def save_conversation(self, tenant_id: str, session_id: str, message: dict):
        """テナント分離された会話履歴の保存"""
        try:
            self.table.put_item(
                Item={
                    'PK': f"TENANT#{tenant_id}#SESSION#{session_id}",
                    'SK': f"MSG#{message['timestamp']}",
                    'tenant_id': tenant_id,
                    'session_id': session_id,
                    'message': message
                },
                ConditionExpression='attribute_not_exists(PK)'
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                raise
    
    def get_conversation_history(self, tenant_id: str, session_id: str) -> list:
        """テナント分離された会話履歴の取得"""
        response = self.table.query(
            KeyConditionExpression='PK = :pk',
            ExpressionAttributeValues={
                ':pk': f"TENANT#{tenant_id}#SESSION#{session_id}"
            }
        )
        return response.get('Items', [])
