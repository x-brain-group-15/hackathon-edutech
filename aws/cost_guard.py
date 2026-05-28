import os
import boto3
import logging
import json
import re

# Cấu hình Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Khởi tạo các AWS Clients
lambda_client = boto3.client('lambda')
iam_client = boto3.client('iam')

# Lấy thông tin tài nguyên từ các biến môi trường được cấu hình trong template.yaml
STUDYBOT_BACKEND_LAMBDA = os.getenv('STUDYBOT_BACKEND_LAMBDA')   # query function
STUDYBOT_UPLOAD_LAMBDA = os.getenv('STUDYBOT_UPLOAD_LAMBDA')
STUDYBOT_CORE_LAMBDA = os.getenv('STUDYBOT_CORE_LAMBDA')
APP_IAM_ROLE_NAME = os.getenv('APP_IAM_ROLE_NAME')
DENY_POLICY_ARN = os.getenv('DENY_POLICY_ARN')

# Tất cả các Lambda cần bị freeze khi vượt ngưỡng 80%
ALL_BACKEND_LAMBDAS = [f for f in [
    STUDYBOT_BACKEND_LAMBDA,
    STUDYBOT_UPLOAD_LAMBDA,
    STUDYBOT_CORE_LAMBDA,
] if f]

def extract_threshold(sns_message):
    """
    Trích xuất ngưỡng chi phí vượt qua (30%, 50%, 80%) từ tin nhắn của AWS Budgets.
    """
    logger.info(f"Analyzing SNS Message: {sns_message}")
    
    # Tìm kiếm mẫu phần trăm ví dụ: "30.0%", "30%", "50%"
    match = re.search(r'(\d+(?:\.\d+)?)\s*%', sns_message)
    if match:
        try:
            val = float(match.group(1))
            logger.info(f"Extracted percentage value: {val}%")
            if 25 <= val <= 35:
                return 30
            elif 45 <= val <= 55:
                return 50
            elif 75 <= val <= 85:
                return 80
        except ValueError:
            pass
            
    # Dự phòng tìm kiếm chuỗi trực tiếp nếu regex không khớp
    sns_message_lower = sns_message.lower()
    if "30%" in sns_message_lower or "30.0" in sns_message_lower:
        return 30
    elif "50%" in sns_message_lower or "50.0" in sns_message_lower:
        return 50
    elif "80%" in sns_message_lower or "80.0" in sns_message_lower:
        return 80
        
    return None

def lambda_handler(event, context):
    logger.info(f"Cost Guard Lambda activated with event: {json.dumps(event)}")
    
    # 1. Trích xuất tin nhắn SNS từ sự kiện kích hoạt
    try:
        records = event.get('Records', [])
        if not records:
            logger.warning("No records found in the event.")
            return {'statusCode': 400, 'body': 'No SNS records found.'}
            
        sns_message = records[0].get('Sns', {}).get('Message', '')
        if not sns_message:
            logger.warning("Empty SNS Message.")
            return {'statusCode': 400, 'body': 'SNS Message is empty.'}
    except Exception as e:
        logger.error(f"Error parsing event: {str(e)}")
        return {'statusCode': 500, 'body': f"Event parsing error: {str(e)}"}

    # 2. Xác định ngưỡng ngân sách bị vượt qua
    threshold = extract_threshold(sns_message)
    if not threshold:
        logger.warning("Could not determine threshold. Defaulting to 80% safety protocol.")
        threshold = 80 # Mặc định kích hoạt đóng băng hệ thống để bảo đảm an toàn
        
    logger.info(f"--- ACTIVE THRESHOLD ACTION TRIGGERED: {threshold}% ---")
    
    # 3. Xử lý phân cấp theo ngưỡng
    if threshold == 30:
        msg = f"[WARN - COST CONTROL] Ngân sách StudyBot vượt mốc 30%! Chi tiết: {sns_message[:200]}..."
        logger.warning(msg)
        print(msg)
        return {
            'statusCode': 200,
            'body': 'Threshold 30% warning logged successfully.'
        }
        
    elif threshold == 50:
        msg = f"[CRITICAL - COST CONTROL] Ngân sách StudyBot vượt mốc 50%! Cần kiểm tra hoạt động tài khoản. Chi tiết: {sns_message[:200]}..."
        logger.error(msg)
        print(msg)
        return {
            'statusCode': 200,
            'body': 'Threshold 50% critical alert logged successfully.'
        }
        
    elif threshold >= 80:
        logger.error("!!! EMERGENCY STOP ACTIVATED (80%+) !!!")
        
        # A. Đóng băng compute: Đặt Reserved Concurrency của tất cả Lambda về 0
        if ALL_BACKEND_LAMBDAS:
            for fn_name in ALL_BACKEND_LAMBDAS:
                try:
                    logger.info(f"Setting reserved concurrency of '{fn_name}' to 0...")
                    lambda_client.put_function_concurrency(
                        FunctionName=fn_name,
                        ReservedConcurrentExecutions=0
                    )
                    logger.info(f"Lambda '{fn_name}' successfully locked.")
                except Exception as e:
                    logger.error(f"Failed to freeze Lambda '{fn_name}': {str(e)}")
        else:
            logger.error("No Lambda function names configured.")
            
        # B. Khóa quyền: Đính kèm chính sách Deny Policy vào Lambda execution IAM role
        if DENY_POLICY_ARN and APP_IAM_ROLE_NAME:
            try:
                logger.info(f"Attaching Deny Policy '{DENY_POLICY_ARN}' to IAM Role '{APP_IAM_ROLE_NAME}'...")
                iam_client.attach_role_policy(
                    RoleName=APP_IAM_ROLE_NAME,
                    PolicyArn=DENY_POLICY_ARN
                )
                logger.info("IAM Deny Policy successfully attached. AWS permissions are restricted.")
            except Exception as e:
                logger.error(f"Failed to attach Deny Policy to IAM Role: {str(e)}")
        else:
            logger.error(f"Missing DENY_POLICY_ARN ({DENY_POLICY_ARN}) or APP_IAM_ROLE_NAME ({APP_IAM_ROLE_NAME}).")
            
        # C. Dọn dẹp khẩn cấp OpenSearch Serverless để chặn đứng chi phí OCU duy trì (~$414/tháng)
        try:
            logger.info("Emergency check for active OpenSearch Serverless collections...")
            aoss_client = boto3.client('opensearchserverless')
            collections = aoss_client.list_collections().get('collectionSummaries', [])
            for col in collections:
                col_id = col.get('id')
                col_name = col.get('name')
                col_status = col.get('status')
                if col_status != 'DELETING':
                    logger.warning(f"!!! EMERGENCY REMEDIATION: Deleting OpenSearch Serverless Collection '{col_name}' ({col_id}) !!!")
                    aoss_client.delete_collection(id=col_id)
                    logger.info(f"Successfully sent deletion command for collection '{col_name}'.")
        except Exception as e:
            logger.warning(f"No OpenSearch Serverless collections modified or API failed: {str(e)}")
            
        return {
            'statusCode': 200,
            'body': 'Threshold 80% EMERGENCY SYSTEM FREEZE executed successfully.'
        }

    return {
        'statusCode': 200,
        'body': 'Threshold processed without specific actions.'
    }
