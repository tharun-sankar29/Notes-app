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

    def get_user_folder(self, user_email):
        """Generate a folder path for the user's notes"""
        # Sanitize email to create a valid folder name
        import re
        safe_email = re.sub(r'[^a-zA-Z0-9@._-]', '_', user_email)
        return f"{self.notes_folder}{safe_email}/"

    def upload_note(self, note_data):
        """Upload a note to S3 in the user's folder"""
        try:
            note_id = str(note_data.get('id'))
            user_email = note_data.get('user_email')
            if not user_email:
                raise ValueError("Note data must include user_email")
                
            file_key = f"{self.get_user_folder(user_email)}{note_id}.json"
            
            logger.info(f"Preparing to upload note. ID: {note_id}, Data: {note_data}")
            
            # Ensure all values are JSON serializable
            serializable_data = {}
            for k, v in note_data.items():
                try:
                    json.dumps({k: v})  # Test serialization
                    serializable_data[k] = v
                except (TypeError, OverflowError) as e:
                    logger.warning(f"Non-serializable data in note {note_id}, field {k}: {str(e)}")
                    serializable_data[k] = str(v)
            
            # Convert note data to JSON string
            note_json = json.dumps(serializable_data, indent=2)
            
            logger.info(f"Uploading note {note_id} to S3 bucket {self.bucket_name}, key: {file_key}")
            
            # Upload to S3
            response = self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=note_json,
                ContentType='application/json'
            )
            
            logger.info(f"Successfully uploaded note {note_id} to S3. Response: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading note to S3: {str(e)}", exc_info=True)
            return False

    def get_user_notes(self, user_email):
        """Get all notes for a specific user from S3"""
        try:
            user_folder = self.get_user_folder(user_email)
            logger.info(f"Fetching notes for user {user_email} from S3 folder: {user_folder}")
            notes = []
            
            try:
                # List all objects in the user's folder
                paginator = self.s3_client.get_paginator('list_objects_v2')
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=user_folder):
                    logger.debug(f"Processing S3 page: {page}")
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            if obj['Key'].endswith('.json'):  # Only process JSON files
                                try:
                                    logger.debug(f"Processing S3 object: {obj['Key']}")
                                    # Get the object
                                    response = self.s3_client.get_object(Bucket=self.bucket_name, Key=obj['Key'])
                                    note_data = json.loads(response['Body'].read().decode('utf-8'))
                                    logger.debug(f"Successfully loaded note: {note_data.get('id')}")
                                    notes.append(note_data)
                                except Exception as e:
                                    logger.error(f"Error processing {obj['Key']}: {str(e)}", exc_info=True)
                                    continue
                    else:
                        logger.warning(f"No contents found in user folder: {user_folder}")
                        break  # No need to continue pagination if no contents found
                        
            except self.s3_client.exceptions.NoSuchKey:
                logger.info(f"No folder found for user {user_email}, returning empty list")
                return []
            except Exception as e:
                logger.error(f"Error listing objects in S3: {str(e)}", exc_info=True)
                return []
                
            logger.info(f"Successfully retrieved {len(notes)} notes for user {user_email}")
            return notes
            
        except Exception as e:
            logger.error(f"Error in get_user_notes: {str(e)}", exc_info=True)
            return []
            
    # Keep the old get_all_notes for admin purposes, but mark as deprecated
    def get_all_notes(self):
        """[Deprecated] Get all notes from S3 (use get_user_notes instead)"""
        logger.warning("get_all_notes() is deprecated. Use get_user_notes(user_email) instead.")
        return []

    def delete_note(self, note_id, user_email):
        """Delete a note from user's S3 folder"""
        try:
            file_key = f"{self.get_user_folder(user_email)}{note_id}.json"
            response = self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            logger.info(f"Successfully deleted note {note_id} for user {user_email}")
            return True
        except Exception as e:
            logger.error(f"Unexpected error in delete_note: {str(e)}", exc_info=True)
            return False
