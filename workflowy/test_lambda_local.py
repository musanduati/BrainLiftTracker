#!/usr/bin/env python3
"""
Local test script to mimic Lambda execution
Supports testing both:
1. Regular Workflowy processing + tweet posting (default)
2. Bulk URL processing (adds to both URLS_CONFIG_TABLE and USER_MAPPING_TABLE)
"""

import os
import sys
import json
import argparse
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

def create_scheduled_event():
    """Create a mock scheduled event for regular processing"""
    return {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
        "time": "2024-01-01T12:00:00Z"
    }

def create_bulk_url_event():
    """Create a mock event with bulk URL data"""

    # Basic Test Account
    bulk_urls = [
        {
            "brainlift": "https://workflowy.com/s/wfx-test-sanket/bjSyw1MzswiIsciE",
            "account_id": "3" # Optional
        }
    ]
    
    return {
        "httpMethod": "POST",
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(bulk_urls)
    }

def create_custom_bulk_url_event(custom_file):
    """Create a bulk URL event from a custom JSON file"""
    try:
        with open(custom_file, 'r') as f:
            bulk_urls = json.load(f)
        
        return {
            "httpMethod": "POST",
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(bulk_urls)
        }
    except Exception as e:
        print(f"❌ Error loading custom file {custom_file}: {e}")
        return None

def display_regular_results(result):
    """Display results for regular Workflowy processing"""
    if isinstance(result.get('body'), str):
        try:
            body_data = json.loads(result['body'])
            print("\n📊 REGULAR PROCESSING SUMMARY:")
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

def display_bulk_url_results(result):
    """Display results for bulk URL processing"""
    if isinstance(result.get('body'), str):
        try:
            body_data = json.loads(result['body'])
            print(f"\n🔗 BULK URL PROCESSING SUMMARY:")
            print(f"Status Code: {result['statusCode']}")
            
            if 'error' in body_data:
                print(f"❌ Error: {body_data['error']}")
            else:
                print(f"Operation: {body_data.get('operation', 'Unknown')}")
                print(f"Total Processed: {body_data.get('total_processed', 0)}")
                
                # URL Config results
                url_config = body_data.get('url_config', {})
                print(f"\n📋 URL CONFIG TABLE:")
                print(f"  - Successful: {url_config.get('successful', 0)}")
                print(f"  - Failed: {url_config.get('failed', 0)}")
                
                # User Mapping results  
                user_mapping = body_data.get('user_mapping', {})
                print(f"\n👥 USER MAPPING TABLE:")
                print(f"  - Successful: {user_mapping.get('successful', 0)}")
                print(f"  - Failed: {user_mapping.get('failed', 0)}")
                
                # Show successful URLs
                if url_config.get('successful_urls'):
                    print(f"\n✅ SUCCESSFULLY ADDED URL CONFIGS:")
                    for url_info in url_config['successful_urls']:
                        print(f"  • {url_info['name']} (ID: {url_info['url_id']}) - Account: {url_info['account_id']}")
                        print(f"    URL: {url_info['url']}")
                
                # Show successful mappings
                if user_mapping.get('successful_mappings'):
                    print(f"\n✅ SUCCESSFULLY ADDED USER MAPPINGS:")
                    for mapping_info in user_mapping['successful_mappings']:
                        print(f"  • {mapping_info['user_name']} -> Account {mapping_info['account_id']}")
                
                # Show failed URLs
                if url_config.get('failed_urls'):
                    print(f"\n❌ FAILED URL CONFIGS:")
                    for url_info in url_config['failed_urls']:
                        print(f"  • Error: {url_info['error']}")
                        if 'url' in url_info:
                            print(f"    URL: {url_info['url']}")
                
                # Show failed mappings
                if user_mapping.get('failed_mappings'):
                    print(f"\n❌ FAILED USER MAPPINGS:")
                    for mapping_info in user_mapping['failed_mappings']:
                        print(f"  • Error: {mapping_info['error']}")
                        if 'user_name' in mapping_info:
                            print(f"    User: {mapping_info['user_name']}")
            
            # Show detailed results
            print(f"\n📋 DETAILED RESULTS:")
            print(json.dumps(body_data, indent=2, default=str))
            
        except json.JSONDecodeError:
            print(f"Raw response body: {result.get('body')}")
    else:
        print(f"Full result: {json.dumps(result, indent=2, default=str)}")

def main():
    """Main function to test Lambda locally"""
    parser = argparse.ArgumentParser(description="Test Workflowy Lambda function locally")
    parser.add_argument(
        "mode", 
        choices=["regular", "bulk", "bulk-small", "bulk-medium", "bulk-large"],
        nargs="?",
        default="regular",
        help="Test mode: regular (default), bulk, bulk-small, bulk-medium, bulk-large"
    )
    parser.add_argument(
        "--custom-file",
        type=str,
        help="Path to custom JSON file with bulk URLs (for bulk mode)"
    )
    
    args = parser.parse_args()
    
    print("🏠 Running Lambda function locally...")
    print("="*50)
    
    # Create appropriate event based on mode
    if args.mode == "regular":
        print("🔄 Testing REGULAR Workflowy processing + tweet posting...")
        mock_event = create_scheduled_event()
    elif args.custom_file:
        print(f"🔗 Testing BULK URL processing with custom file: {args.custom_file}...")
        mock_event = create_custom_bulk_url_event(args.custom_file)
        if mock_event is None:
            return 1
    else:
        print(f"🔗 Testing BULK URL processing")
        mock_event = create_bulk_url_event()
    
    mock_context = create_mock_lambda_context()
    
    try:
        # Call the lambda handler
        result = lambda_handler(mock_event, mock_context)
        
        print("\n" + "="*50)
        print("✅ Lambda execution completed successfully!")
        print("="*50)
        
        # Display results based on mode
        if args.mode == "regular":
            display_regular_results(result)
        else:
            display_bulk_url_results(result)
            
    except Exception as e:
        print(f"\n❌ Lambda execution failed!")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    print("🧪 Workflowy Lambda Local Tester")
    print("Available modes:")
    print("  regular      - Test regular Workflowy processing + tweet posting (default)")
    print("  bulk-small   - Test bulk URL processing with 3 sample URLs (some with account_id)")
    print("  bulk-medium  - Test bulk URL processing with 8 sample URLs") 
    print("  bulk-large   - Test bulk URL processing with 20 sample URLs")
    print("  bulk --custom-file <path> - Test bulk URL processing with custom JSON file")
    print("Usage examples:")
    print("  python test_lambda_local.py")
    print("  python test_lambda_local.py regular")
    print("  python test_lambda_local.py bulk-small")
    print("  python test_lambda_local.py bulk --custom-file my_urls.json")
    
    exit_code = main()
    sys.exit(exit_code)
