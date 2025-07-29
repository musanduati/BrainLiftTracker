# aws_storage.py - New file to replace local file operations
import boto3
import json
from typing import Dict, List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class AWSStorage:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        
        # Get from environment variables (set these manually in Lambda/EC2)
        self.bucket_name = os.environ.get('WORKFLOWY_BUCKET', 'workflowy-content-test')
        self.state_table_name = os.environ.get('STATE_TABLE', 'workflowy-state-table-test')
        self.state_table = self.dynamodb.Table(self.state_table_name)
    
    def save_scraped_content(self, user_name: str, content: str, timestamp: str) -> str:
        """Replace: user_dir / f"{user_name}_scraped_workflowy_{timestamp}.txt" """
        # OLD: key = f"scraped_content/{user_name}/{user_name}_scraped_workflowy_{timestamp}.txt"
        key = f"{user_name}/scraped_content/{user_name}_scraped_workflowy_{timestamp}.txt"

        print("Bucket name: ", self.bucket_name)
        
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content,
            ContentType='text/plain'
        )
        
        return f"s3://{self.bucket_name}/{key}"
    
    def save_change_tweets(self, user_name: str, tweets: List[Dict], timestamp: str) -> str:
        """Replace: user_dir / f"{user_name}_change_tweets_{timestamp}.json" """
        # OLD: key = f"change_tweets/{user_name}/{user_name}_change_tweets_{timestamp}.json"
        key = f"{user_name}/change_tweets/{user_name}_change_tweets_{timestamp}.json"
        
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(tweets, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        return f"s3://{self.bucket_name}/{key}"
    
    def load_previous_state(self, user_name: str) -> Dict:
        """Replace: load_previous_state(user_dir) """
        try:
            response = self.state_table.get_item(
                Key={'user_name': user_name}
            )
            item = response.get('Item', {})
            state = item.get('state', {"dok4": [], "dok3": []})
            
            # Ensure the state has the expected structure
            if not isinstance(state, dict):
                print(f"Warning: Invalid state format for {user_name}, resetting to default")
                return {"dok4": [], "dok3": []}
            
            # Ensure both keys exist
            if "dok4" not in state:
                state["dok4"] = []
            if "dok3" not in state:
                state["dok3"] = []
                
            return state
            
        except Exception as e:
            print(f"Error loading state for {user_name}: {e}")
            return {"dok4": [], "dok3": []}
    
    def save_current_state(self, user_name: str, state: Dict):
        """Replace: save_current_state(user_dir, current_state) """
        self.state_table.put_item(
            Item={
                'user_name': user_name,
                'state': state,
                'last_updated': datetime.now().isoformat(),
                'ttl': int(datetime.now().timestamp()) + (365 * 24 * 60 * 60)  # 1 year
            }
        )
    
    def is_first_run(self, user_name: str) -> bool:
        """Replace: is_first_run() """
        try:
            response = self.state_table.get_item(
                Key={'user_name': user_name}
            )
            return 'Item' not in response
        except:
            return True



