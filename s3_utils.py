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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class S3Manager:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION')
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.notes_folder = os.getenv('S3_NOTES_FOLDER', 'notes/')

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
            print(f"Error uploading note to S3: {e}")
            return False

    def get_all_notes(self):
        """Retrieve all notes from S3"""
        try:
            notes = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.notes_folder):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['Key'].endswith('.json'):
                            response = self.s3_client.get_object(
                                Bucket=self.bucket_name,
                                Key=obj['Key']
                            )
                            note_data = json.loads(response['Body'].read().decode('utf-8'))
                            notes.append(note_data)
            
            # Sort notes by creation date (newest first)
            return sorted(notes, key=lambda x: x.get('createdAt', ''), reverse=True)
            
        except (NoCredentialsError, ClientError) as e:
            print(f"Error retrieving notes from S3: {e}")
            return []

    def delete_note(self, note_id):
        """Delete a note from S3"""
        try:
            file_key = f"{self.notes_folder}{note_id}.json"
            logger.info(f"Deleting note from S3 - ID: {note_id}")
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            logger.info(f"Successfully deleted note from S3 - ID: {note_id}")
            return True
        except (NoCredentialsError, ClientError) as e:
            print(f"Error deleting note from S3: {e}")
            return False
