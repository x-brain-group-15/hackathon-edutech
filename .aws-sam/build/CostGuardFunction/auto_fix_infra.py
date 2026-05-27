import boto3
import logging
import json

# Cấu hình Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Khởi tạo các AWS Clients
ec2_client = boto3.client('ec2')
rds_client = boto3.client('rds')

# Whitelist các cấu hình tài nguyên nhỏ/được cho phép cho Hackathon
ALLOWED_EC2_TYPES = ['t2.micro', 't3.micro']
ALLOWED_RDS_CLASSES = ['db.t3.micro', 'db.t4g.micro']

def lambda_handler(event, context):
    logger.info(f"Auto Fix Infra Lambda activated by EventBridge: {json.dumps(event)}")
    
    detail = event.get('detail', {})
    event_name = detail.get('eventName')
    
    # 1. Phát hiện và xử lý sự kiện tạo EC2 Instance (RunInstances)
    if event_name == 'RunInstances':
        try:
            items = detail.get('responseElements', {}).get('instancesSet', {}).get('items', [])
            for item in items:
                instance_id = item.get('instanceId')
                instance_type = item.get('instanceType')
                
                if instance_type not in ALLOWED_EC2_TYPES:
                    logger.warning(f"!!! CRITICAL WARNING: Unauthorized EC2 Instance Type '{instance_type}' detected for '{instance_id}' !!!")
                    logger.info(f"Auto Fix: Terminating unauthorized instance '{instance_id}' immediately...")
                    
                    ec2_client.terminate_instances(InstanceIds=[instance_id])
                    logger.info(f"Successfully terminated instance '{instance_id}'.")
                else:
                    logger.info(f"EC2 Instance '{instance_id}' with type '{instance_type}' is whitelisted. No action taken.")
        except Exception as e:
            logger.error(f"Error terminating EC2 instance: {str(e)}")
            
    # 2. Phát hiện và xử lý sự kiện tạo RDS DB Instance (CreateDBInstance)
    elif event_name == 'CreateDBInstance':
        try:
            db_instance_id = detail.get('requestParameters', {}).get('dBInstanceIdentifier')
            db_class = detail.get('requestParameters', {}).get('dBInstanceClass')
            
            if db_class not in ALLOWED_RDS_CLASSES:
                logger.warning(f"!!! CRITICAL WARNING: Unauthorized RDS Class '{db_class}' detected for '{db_instance_id}' !!!")
                logger.info(f"Auto Fix: Deleting unauthorized RDS DB Instance '{db_instance_id}' immediately...")
                
                # Delete RDS Database instance và bỏ qua việc chụp snapshot cuối cùng để hoàn tất nhanh nhất
                rds_client.delete_db_instance(
                    DBInstanceIdentifier=db_instance_id,
                    SkipFinalSnapshot=True
                )
                logger.info(f"Successfully sent deletion command for RDS Database '{db_instance_id}'.")
            else:
                logger.info(f"RDS Database '{db_instance_id}' class '{db_class}' is whitelisted. No action taken.")
        except Exception as e:
            logger.error(f"Error deleting RDS instance: {str(e)}")
            
    # 3. Phát hiện và xử lý sự kiện tạo OpenSearch Serverless (CreateCollection)
    elif event_name == 'CreateCollection':
        try:
            collection_name = detail.get('requestParameters', {}).get('name')
            logger.warning(f"!!! CRITICAL WARNING: OpenSearch Serverless Collection '{collection_name}' creation detected !!!")
            logger.info("Auto Fix: Fetching collection ID for emergency deletion to prevent massive idle billing ($414/month)...")
            
            aoss_client = boto3.client('opensearchserverless')
            # Lọc tìm collection theo tên vừa tạo
            collections = aoss_client.list_collections(
                collectionFilters={'name': collection_name}
            ).get('collectionSummaries', [])
            
            for col in collections:
                col_id = col.get('id')
                col_status = col.get('status')
                if col_status != 'DELETING':
                    logger.warning(f"Auto Fix: Deleting OpenSearch Collection '{collection_name}' ({col_id}) immediately...")
                    aoss_client.delete_collection(id=col_id)
                    logger.info(f"Successfully deleted unauthorized OpenSearch Collection '{collection_name}'.")
        except Exception as e:
            logger.error(f"Error deleting unauthorized OpenSearch Serverless Collection: {str(e)}")
            
    return {
        'statusCode': 200,
        'body': 'Auto Fix Infra inspection completed.'
    }
