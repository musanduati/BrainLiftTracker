#!/usr/bin/env python3
"""
Local test script to mimic Lambda execution
"""

import os
import sys
import json
from pathlib import Path

# Add the workflowy directory to Python path
workflowy_dir = Path(__file__).parent / "workflowy"
sys.path.insert(0, str(workflowy_dir))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import the lambda handler
from lambda_handler import lambda_handler

def create_mock_lambda_context():
    """Create a mock Lambda context object"""
    class MockContext:
        def __init__(self):
            self.function_name = "workflowy-processor"
            self.function_version = "$LATEST"
            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:workflowy-processor"
            self.memory_limit_in_mb = "512"
            self.remaining_time_in_millis = lambda: 300000  # 5 minutes
            self.log_group_name = "/aws/lambda/workflowy-processor"
            self.log_stream_name = "2024/01/01/[$LATEST]abc123"
            self.aws_request_id = "local-test-12345"

    return MockContext()

def main():
    """Main function to test Lambda locally"""
    print("🏠 Running Lambda function locally...")
    print("="*50)
    
    # Create mock event and context (Lambda handler doesn't actually use them)
    mock_event = {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
        "time": "2024-01-01T12:00:00Z"
    }
    
    mock_context = create_mock_lambda_context()
    
    try:
        # Call the lambda handler
        result = lambda_handler(mock_event, mock_context)
        
        print("\n" + "="*50)
        print("✅ Lambda execution completed successfully!")
        print("="*50)
        
        # Pretty print the results
        if isinstance(result.get('body'), str):
            try:
                body_data = json.loads(result['body'])
                print("\n📊 EXECUTION SUMMARY:")
                print(f"Status Code: {result['statusCode']}")
                print(f"Scraping Results: {len(body_data.get('scraping', {}).get('results', []))}")
                print(f"  - Successful: {body_data.get('scraping', {}).get('successful', 0)}")
                print(f"  - Failed: {body_data.get('scraping', {}).get('failed', 0)}")
                print(f"Posting Results: {len(body_data.get('posting', {}).get('results', []))}")
                print(f"  - Successful: {body_data.get('posting', {}).get('successful', 0)}")
                print(f"  - Failed: {body_data.get('posting', {}).get('failed', 0)}")
                
                # Show detailed results
                print(f"\n📋 DETAILED RESULTS:")
                print(json.dumps(body_data, indent=2, default=str))
                
            except json.JSONDecodeError:
                print(f"Raw response body: {result.get('body')}")
        else:
            print(f"Full result: {json.dumps(result, indent=2, default=str)}")
            
    except Exception as e:
        print(f"\n❌ Lambda execution failed!")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
