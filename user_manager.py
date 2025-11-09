import boto3
from boto3.dynamodb.conditions import Key
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

class UserManager:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb',
                                     region_name=os.getenv('AWS_REGION', 'us-west-2'),
                                     aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                                     aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
        self.table_name = 'NotesAppUsers'
        self.table = self.dynamodb.Table(self.table_name)
        self._create_table_if_not_exists()

    def _create_table_if_not_exists(self):
        try:
            existing_tables = self.dynamodb.meta.client.list_tables()['TableNames']
            if self.table_name not in existing_tables:
                self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {'AttributeName': 'email', 'KeyType': 'HASH'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'email', 'AttributeType': 'S'}
                    ],
                    ProvisionedThroughput={
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                )
                self.table.meta.client.get_waiter('table_exists').wait(TableName=self.table_name)
        except Exception as e:
            print(f"Error creating table: {e}")

    def create_user(self, name, email, password):
        try:
            # Check if user already exists
            response = self.table.get_item(Key={'email': email})
            if 'Item' in response:
                return False, "Email already registered"
                
            # Create new user
            self.table.put_item(
                Item={
                    'email': email,
                    'name': name,
                    'password': generate_password_hash(password),
                    'created_at': str(datetime.utcnow())
                }
            )
            return True, "User created successfully"
        except Exception as e:
            return False, str(e)

    def verify_user(self, email, password):
        try:
            response = self.table.get_item(Key={'email': email})
            if 'Item' not in response:
                return None, "User not found"
                
            user = response['Item']
            if check_password_hash(user['password'], password):
                return {'email': user['email'], 'name': user['name']}, None
            return None, "Invalid password"
        except Exception as e:
            return None, str(e)

    def get_user(self, email):
        try:
            response = self.table.get_item(Key={'email': email})
            if 'Item' not in response:
                return None
            return response['Item']
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
