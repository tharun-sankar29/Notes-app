import os
import json
import boto3
import logging
from datetime import datetime
from botocore.exceptions import NoCredentialsError, ClientError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('s3_utils.log')
    ]
)
logger = logging.getLogger(__name__)

class S3Manager:
    def __init__(self):
        """Initialize the S3 manager with credentials from environment variables"""
        load_dotenv()  # Load environment variables from .env file
        
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region_name = os.getenv('AWS_DEFAULT_REGION', 'ap-south-1')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.notes_folder = os.getenv('S3_NOTES_FOLDER', 'notes/')
        
        # Validate required environment variables
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name]):
            error_msg = "Missing required AWS configuration in environment variables"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Ensure notes folder ends with a slash
        if not self.notes_folder.endswith('/'):
            self.notes_folder += '/'
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
            logger.info("S3 client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise

    def upload_note(self, note_data):
        """Upload a single note to S3"""
        try:
            note_id = str(note_data.get('id', datetime.utcnow().timestamp()))
            file_key = f"{self.notes_folder}{note_id}.json"
            
            logger.info(f"Uploading note to S3 - ID: {note_id}, Title: {note_data.get('title', 'Untitled')}")
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=json.dumps(note_data, indent=2),
                ContentType='application/json'
            )
            
            logger.info(f"Successfully uploaded note to S3 - ID: {note_id}")
            return True
        except (NoCredentialsError, ClientError) as e:
            logger.error(f"Error uploading note to S3: {str(e)}")
            return False

    def get_all_notes(self):
        """Retrieve all notes from S3"""
        try:
            if not self.bucket_name:
                logger.error("Bucket name is not set")
                return []

            logger.info(f"Listing objects in bucket: {self.bucket_name}, folder: {self.notes_folder}")
            
            notes = []
            try:
                paginator = self.s3_client.get_paginator('list_objects_v2')
                
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.notes_folder):
                    if 'Contents' not in page:
                        logger.info("No notes found in the bucket")
                        return []
                        
                    for obj in page['Contents']:
                        if not obj['Key'].endswith('/'):  # Skip directories
                            try:
                                response = self.s3_client.get_object(
                                    Bucket=self.bucket_name,
                                    Key=obj['Key']
                                )
                                note_data = json.loads(response['Body'].read().decode('utf-8'))
                                notes.append(note_data)
                                logger.debug(f"Successfully retrieved note: {obj['Key']}")
                            except (ClientError, json.JSONDecodeError) as e:
                                logger.error(f"Error processing note {obj['Key']}: {str(e)}")
                                continue
                
                logger.info(f"Successfully retrieved {len(notes)} notes")
                return sorted(notes, key=lambda x: x.get('createdAt', ''), reverse=True)
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', 'Unknown error')
                logger.error(f"AWS Error - Code: {error_code}, Message: {error_message}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error in get_all_notes: {str(e)}", exc_info=True)
            return []

    def delete_note(self, note_id):
        """Delete a note from S3"""
        try:
            if not self.bucket_name:
                logger.error("Bucket name is not set")
                return False
                
            if not note_id:
                logger.error("No note ID provided for deletion")
                return False
                
            file_key = f"{self.notes_folder}{note_id}.json"
            logger.info(f"Deleting note from S3 - ID: {note_id}")
            
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
                
                logger.info(f"Successfully deleted note from S3 - ID: {note_id}")
                return True
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', 'Unknown error')
                if error_code == 'NoSuchKey':
                    logger.warning(f"Note not found in S3 - ID: {note_id}")
                else:
                    logger.error(f"Failed to delete note from S3 - Code: {error_code}, Message: {error_message}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error in delete_note: {str(e)}", exc_info=True)
            return False
