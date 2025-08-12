# aws_wrapper.py
#!/usr/bin/env python3
"""
AWS wrapper for batch_automation.py
Handles both CSV files and AWS S3 reporting
"""

import os
import json
import boto3
import sys
import csv
from datetime import datetime
from pathlib import Path

# Add auto-approver to path
sys.path.append('/app/auto-approver')
from batch_automation import BatchTwitterAutomation

class AWSBatchWrapper(BatchTwitterAutomation):
    def __init__(self):
        # Initialize AWS clients
        self.s3 = boto3.client('s3')
        
        # Get configuration from environment
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        
        # Initialize parent class
        super().__init__(
            accounts_file=None,  # We'll load from CSV files
            headless=True,       # Always headless in container
            browser="chrome"
        )
        
        self.batch_id = f"fargate-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
    def load_accounts_from_csv_files(self):
        """Load accounts from CSV files (test or production)"""
        all_accounts = []
        
        # Check if we're in test mode
        test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
        
        print(f"🔍 TEST_MODE environment variable: {os.environ.get('TEST_MODE', 'not set')}")
        print(f"🔍 Detected test_mode: {test_mode}")
        
        if test_mode:
            # Test mode: use only the test file
            csv_files = [
                '/app/auto-approver/accounts_test.csv'
            ]
            print("🧪 RUNNING IN TEST MODE - Processing 1 test account")
        else:
            # Production mode: use both production files
            csv_files = [
                '/app/auto-approver/academics_accounts.csv',
                '/app/auto-approver/superbuilders_accounts.csv'
            ]
            print("🚀 RUNNING IN PRODUCTION MODE - Processing all accounts")
        
        for csv_file in csv_files:
            if os.path.exists(csv_file):
                print(f"Loading accounts from {csv_file}...")
                accounts = self._load_single_csv(csv_file)
                all_accounts.extend(accounts)
                print(f"Loaded {len(accounts)} accounts from {Path(csv_file).name}")
            else:
                print(f"Warning: CSV file not found: {csv_file}")
        
        print(f"Total accounts loaded: {len(all_accounts)}")
        return all_accounts
    
    def _load_single_csv(self, csv_file):
        """Load accounts from a single CSV file"""
        accounts = []
        
        try:
            with open(csv_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    account = {
                        'username': row.get('username', '').strip(),
                        'password': row.get('password', '').strip(),
                        'email': row.get('email', '').strip() if row.get('email') else None,
                        'max_approvals': int(row.get('max_approvals', 50)),
                        'delay_seconds': int(row.get('delay_seconds', 3)),
                        'source_file': Path(csv_file).name  # Track which file this came from
                    }
                    
                    # Only add accounts with username and password
                    if account['username'] and account['password']:
                        accounts.append(account)
                    else:
                        print(f"Skipping incomplete account row in {Path(csv_file).name}")
                        
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")
            
        return accounts
    
    def load_accounts(self):
        """Override parent method to load from CSV files"""
        self.accounts = self.load_accounts_from_csv_files()
        if not self.accounts:
            raise ValueError("No accounts found in CSV files")
        return self.accounts
    
    def save_results_to_s3(self):
        """Save results to S3 with enhanced reporting"""
        if not self.bucket_name:
            print("No S3 bucket configured, skipping S3 upload")
            self._save_results_locally()
            return
            
        try:
            # Prepare enhanced results summary
            successful = sum(1 for r in self.results if r.get('success', False))
            total_approvals = sum(r.get('approved_count', 0) for r in self.results)
            total_followers_saved = sum(r.get('followers_saved', 0) for r in self.results)
            
            # Group results by source file
            by_source = {}
            for result in self.results:
                source = result.get('source_file', 'unknown')
                if source not in by_source:
                    by_source[source] = {'accounts': 0, 'successful': 0, 'approvals': 0}
                by_source[source]['accounts'] += 1
                if result.get('success', False):
                    by_source[source]['successful'] += 1
                by_source[source]['approvals'] += result.get('approved_count', 0)
            
            results_data = {
                'batch_id': self.batch_id,
                'timestamp': datetime.utcnow().isoformat(),
                'execution_environment': 'AWS_ECS_FARGATE',
                'summary': {
                    'total_accounts': len(self.results),
                    'successful_accounts': successful,
                    'failed_accounts': len(self.results) - successful,
                    'success_rate': round(successful / len(self.results) * 100, 2) if self.results else 0,
                    'total_approvals': total_approvals,
                    'total_followers_saved': total_followers_saved,
                    'by_source_file': by_source
                },
                'detailed_results': self.results
            }
            
            # Save to S3
            timestamp = datetime.utcnow()
            key = f"results/{timestamp.strftime('%Y/%m/%d')}/{self.batch_id}.json"
            
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(results_data, indent=2),
                ContentType='application/json',
                Metadata={
                    'batch-id': self.batch_id,
                    'accounts-processed': str(len(self.results)),
                    'success-rate': str(round(successful / len(self.results) * 100, 2) if self.results else 0),
                    'total-approvals': str(total_approvals)
                }
            )
            
            print(f"\n✅ Results saved to S3: s3://{self.bucket_name}/{key}")
            print(f"📊 Summary: {successful}/{len(self.results)} successful ({(successful/len(self.results)*100):.1f}%)")
            print(f"🎯 Total approvals: {total_approvals}")
            print(f"👥 Total followers saved: {total_followers_saved}")
            
            # Print breakdown by source file
            print(f"\n📁 Breakdown by source file:")
            for source, stats in by_source.items():
                print(f"   {source}: {stats['successful']}/{stats['accounts']} successful, {stats['approvals']} approvals")
            
        except Exception as e:
            print(f"❌ Failed to save results to S3: {e}")
            self._save_results_locally()
    
    def _save_results_locally(self):
        """Save results locally as backup"""
        try:
            results_data = {
                'batch_id': self.batch_id,
                'timestamp': datetime.utcnow().isoformat(),
                'summary': {
                    'total_accounts': len(self.results),
                    'successful_accounts': sum(1 for r in self.results if r.get('success', False)),
                    'total_approvals': sum(r.get('approved_count', 0) for r in self.results)
                },
                'detailed_results': self.results
            }
            
            local_file = f"/tmp/results_{self.batch_id}.json"
            with open(local_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            print(f"💾 Results saved locally: {local_file}")
        except Exception as e:
            print(f"❌ Failed to save results locally: {e}")
    
    def run_aws_batch_automation(self):
        """Run the batch automation with AWS integration"""
        test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
        mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
        csv_files_text = "accounts_test.csv" if test_mode else "academics_accounts.csv, superbuilders_accounts.csv"
        
        print(f"\n{'='*60}")
        print(f"AWS FARGATE TWITTER AUTOMATION - {mode_text}")
        print(f"Batch ID: {self.batch_id}")
        print(f"Start Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Processing CSV files: {csv_files_text}")
        print(f"{'='*60}")
        
        try:
            # Run the standard batch automation
            self.run_batch_automation()
            
            # Save results to S3
            self.save_results_to_s3()
            
            print(f"\n✅ AWS Batch automation completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ AWS Batch automation failed: {str(e)}")
            # Still try to save what we have
            try:
                self.save_results_to_s3()
            except:
                pass
            raise

def main():
    """Main entry point"""
    print("Starting AWS Twitter Automation Wrapper...")
    
    wrapper = AWSBatchWrapper()
    success = wrapper.run_aws_batch_automation()
    
    if success:
        print("✅ Automation completed successfully!")
        exit(0)
    else:
        print("❌ Automation completed with errors!")
        exit(1)

if __name__ == "__main__":
    main()
