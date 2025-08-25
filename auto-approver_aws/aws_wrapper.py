# aws_wrapper.py
#!/usr/bin/env python3
"""
AWS wrapper for batch_automation.py
Handles both CSV files and AWS S3 reporting with email notifications
"""

import os
import json
import boto3
import sys
import csv
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# Add auto-approver to path
sys.path.append('/app/auto-approver')
from batch_automation_enhanced import WorkingEnhancedBatchAutomation
from email_service import AutomationEmailService
from s3_session_manager import S3SessionManager

class AWSBatchWrapper(WorkingEnhancedBatchAutomation):
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
        
        self.batch_id = f"fargate-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        
        # Initialize email service
        self.email_service = AutomationEmailService()
        print(f"📧 Email service initialized: {'✅ Available' if self.email_service.ses_available else '❌ Not available'}")
        if self.email_service.to_emails:
            print(f"   Recipients: {', '.join(self.email_service.to_emails)}")
        else:
            print(f"   ⚠️ No recipients configured")
        
        # Initialize session manager
        self.session_manager = S3SessionManager(bucket_name=self.bucket_name)
        print(f"💾 Session management: {'✅ Available' if self.session_manager.s3_available else '❌ Not available'}")
        
        # Clean up expired sessions at startup
        if self.session_manager.s3_available:
            cleaned = self.session_manager.cleanup_expired_sessions()
            if cleaned > 0:
                print(f"🧹 Cleaned up {cleaned} expired sessions at startup")
    
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
            # Production mode: Use all Production files
            csv_files = [
                '/app/auto-approver/accounts_academics.csv',
                '/app/auto-approver/accounts_superbuilders.csv',
                '/app/auto-approver/accounts_finops.csv',
                '/app/auto-approver/accounts_klair.csv'
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
                'timestamp': datetime.now(timezone.utc).isoformat(),
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
            timestamp = datetime.now(timezone.utc)
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
                'timestamp': datetime.now(timezone.utc).isoformat(),
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
        """Run the batch automation with AWS integration and email notifications"""
        test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
        mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
        csv_files_text = "accounts_test.csv" if test_mode else "academics_accounts.csv, superbuilders_accounts.csv"
        
        print(f"\n{'='*60}")
        print(f"AWS FARGATE TWITTER AUTOMATION - {mode_text}")
        print(f"Batch ID             : {self.batch_id}")
        print(f"Start Time           : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Processing CSV files : {csv_files_text}")
        print(f"{'='*60}")
        
        automation_success = False
        s3_success = False
        email_success = False
        
        try:
            # Run the standard batch automation
            print("\n🔄 Starting batch automation...")
            self.run_batch_automation()
            automation_success = True
            print("✅ Batch automation completed")
            
            # Save results to S3
            print("\n📤 Saving results to S3...")
            self.save_results_to_s3()
            s3_success = True
            print("✅ Results saved to S3")
            
            # Send email notification - NEW
            print("\n📧 Sending email notification...")
            email_success = self._send_completion_email(test_mode)
            
            if email_success:
                print("✅ Email notification sent")
            else:
                print("⚠️ Email notification failed (but automation succeeded)")
            
            print(f"\n✅ AWS Batch automation completed successfully!")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ AWS Batch automation failed: {error_msg}")
            
            # Still try to save what we have
            if not s3_success:
                try:
                    print("🔄 Attempting to save partial results to S3...")
                    self.save_results_to_s3()
                    s3_success = True
                    print("✅ Partial results saved to S3")
                except Exception as s3_error:
                    print(f"❌ Failed to save partial results: {str(s3_error)}")
            
            # Send error notification - NEW
            try:
                print("📧 Sending error notification...")
                self._send_error_email(error_msg, test_mode)
                print("✅ Error notification sent")
            except Exception as email_error:
                print(f"❌ Failed to send error notification: {str(email_error)}")
            
            raise
    
    def _send_completion_email(self, test_mode: bool) -> bool:
        """Send completion email notification"""
        try:
            # Prepare email data in the format expected by email service
            execution_mode = "AWS_ECS_FARGATE_TEST" if test_mode else "AWS_ECS_FARGATE_PRODUCTION"
            
            # Calculate summary statistics
            total_accounts = len(self.results)
            successful_accounts = sum(1 for r in self.results if r.get('success', False))
            failed_accounts = total_accounts - successful_accounts
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
            
            # Create results data structure for email service
            email_data = {
                'batch_id': self.batch_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'execution_environment': execution_mode,
                'summary': {
                    'total_accounts': total_accounts,
                    'successful_accounts': successful_accounts,
                    'failed_accounts': failed_accounts,
                    'success_rate': round(successful_accounts / total_accounts * 100, 2) if total_accounts > 0 else 0,
                    'total_approvals': total_approvals,
                    'total_followers_saved': total_followers_saved,
                    'by_source_file': by_source
                },
                'detailed_results': self.results
            }
            
            # Send email
            return self.email_service.send_completion_notification(email_data, execution_mode)
            
        except Exception as e:
            print(f"❌ Error preparing/sending completion email: {str(e)}")
            print(f"   Traceback: {traceback.format_exc()}")
            return False
    
    def _send_error_email(self, error_message: str, test_mode: bool) -> bool:
        """Send error notification email"""
        try:
            execution_mode = "AWS_ECS_FARGATE_TEST" if test_mode else "AWS_ECS_FARGATE_PRODUCTION"
            
            # Include some context in the error message
            enhanced_error = f"""
Automation Error Details:
========================

Primary Error:
{error_message}

Context:
- Batch ID: {self.batch_id}
- Execution Mode: {execution_mode}
- Processed Accounts: {len(self.results) if hasattr(self, 'results') else 0}
- Error Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

Full Traceback:
{traceback.format_exc()}
"""
            
            return self.email_service.send_error_notification(
                enhanced_error, 
                execution_mode, 
                self.batch_id
            )
            
        except Exception as e:
            print(f"❌ Error sending error notification: {str(e)}")
            return False

    def _get_session_statistics(self) -> Dict[str, Any]:
        """Get session usage statistics"""
        if not hasattr(self, 'session_manager') or not self.session_manager.s3_available:
            return {'session_management': 'disabled'}
        
        try:
            active_sessions = self.session_manager.list_sessions()
            return {
                'session_management': 'enabled',
                'active_sessions_count': len(active_sessions),
                'active_sessions': active_sessions
            }
        except Exception as e:
            return {
                'session_management': 'error',
                'error': str(e)
            }

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
