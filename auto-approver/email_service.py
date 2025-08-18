#!/usr/bin/env python3
"""
AWS SES Email Service for Twitter Automation
Sends completion notifications with detailed results
"""

import boto3
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError

class AutomationEmailService:
    def __init__(self):
        self.ses_region = os.getenv('SES_REGION', 'us-east-1')
        self.from_email = os.getenv('SES_FROM_EMAIL', 'brainlift.monitor@trilogy.com')
        self.to_emails = self._parse_email_list(os.getenv('SES_TO_EMAILS', ''))
        
        # Initialize SES client
        try:
            self.ses_client = boto3.client('ses', region_name=self.ses_region)
            self.ses_available = True
        except (NoCredentialsError, Exception) as e:
            print(f"⚠️ SES not available: {str(e)}")
            self.ses_client = None
            self.ses_available = False
        
    def _parse_email_list(self, email_string: str) -> List[str]:
        """Parse comma-separated email list"""
        if not email_string:
            return []
        return [email.strip() for email in email_string.split(',') if email.strip()]
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in a human-readable way"""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
    
    def _get_status_emoji(self, success: bool) -> str:
        """Get emoji for success status"""
        return "✅" if success else "❌"
    
    def _calculate_stats(self, results_data: Dict) -> Dict[str, Any]:
        """Calculate comprehensive statistics from results"""
        detailed_results = results_data.get('detailed_results', [])
        summary = results_data.get('summary', {})
        
        stats = {
            'total_accounts': len(detailed_results),
            'successful_accounts': summary.get('successful_accounts', 0),
            'failed_accounts': summary.get('failed_accounts', 0),
            'total_approvals': summary.get('total_approvals', 0),
            'success_rate': 0,
            'auth_stats': {},
            'top_performers': [],
            'failed_accounts_details': []
        }
        
        # Calculate success rate
        if stats['total_accounts'] > 0:
            stats['success_rate'] = round((stats['successful_accounts'] / stats['total_accounts']) * 100, 1)
        
        # Authentication statistics
        auth_attempts = 0
        imap_successful = 0
        manual_fallback = 0
        auth_skipped = 0
        
        # Top performers and failed accounts
        successful_results = []
        failed_results = []
        
        for result in detailed_results:
            # Auth stats
            if result.get('auth_code_required'):
                auth_attempts += 1
                auth_method = result.get('auth_method_used')
                if auth_method == 'imap':
                    imap_successful += 1
                elif auth_method == 'manual':
                    manual_fallback += 1
                elif auth_method == 'skipped':
                    auth_skipped += 1
            
            # Performance tracking
            if result.get('success'):
                successful_results.append(result)
            else:
                failed_results.append({
                    'username': result.get('username', 'Unknown'),
                    'error': result.get('error', 'Unknown error'),
                    'duration': result.get('duration_seconds', 0)
                })
        
        # Sort top performers by approval count
        stats['top_performers'] = sorted(
            successful_results, 
            key=lambda x: x.get('approved_count', 0), 
            reverse=True
        )[:5]  # Top 5
        
        stats['failed_accounts_details'] = failed_results[:10]  # First 10 failures
        
        stats['auth_stats'] = {
            'total_attempts': auth_attempts,
            'imap_successful': imap_successful,
            'manual_fallback': manual_fallback,
            'auth_skipped': auth_skipped
        }
        
        return stats
    
    def _create_html_email(self, results_data: Dict, execution_mode: str) -> str:
        """Create rich HTML email content with dark mode compatibility"""
        stats = self._calculate_stats(results_data)
        timestamp = results_data.get('timestamp', datetime.now(timezone.utc).isoformat())
        batch_id = results_data.get('batch_id', 'Unknown')
        
        # Determine overall status
        if stats['success_rate'] >= 90:
            status_color = "#28a745"  # Green
            status_text = "Excellent"
            status_emoji = "🎉"
        elif stats['success_rate'] >= 70:
            status_color = "#ffc107"  # Yellow
            status_text = "Good"
            status_emoji = "👍"
        else:
            status_color = "#dc3545"  # Red
            status_text = "Needs Attention"
            status_emoji = "⚠️"
        
        html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
    <title>Twitter Approval Automation Results</title>
    <style>
        /* Dark mode compatibility */
        :root {{
            color-scheme: light dark;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        
        /* Dark mode styles */
        @media (prefers-color-scheme: dark) {{
            body {{
                color: #ffffff !important;
                background-color: #1a1a1a !important;
            }}
            .container {{
                background-color: #2d2d2d !important;
                border: 1px solid #404040 !important;
            }}
            .content {{
                background-color: #2d2d2d !important;
            }}
            .stat-card {{
                background-color: #3d3d3d !important;
                border-color: #505050 !important;
            }}
            .account-list {{
                background-color: #3d3d3d !important;
            }}
            .account-item {{
                border-bottom-color: #505050 !important;
            }}
            .footer {{
                background-color: #3d3d3d !important;
                border-top-color: #505050 !important;
            }}
            .details-table th {{
                background-color: #3d3d3d !important;
            }}
            .details-table th, .details-table td {{
                border-bottom-color: #505050 !important;
            }}
            .section h3 {{
                border-bottom-color: #505050 !important;
            }}
        }}
        
        .container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
            border: 1px solid #e9ecef;
        }}
        .header {{
            background: linear-gradient(135deg, #1da1f2, #1991db);
            color: white !important;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: white !important;
        }}
        .header .subtitle {{
            margin-top: 8px;
            opacity: 0.9;
            font-size: 14px;
            color: white !important;
        }}
        .content {{
            padding: 30px;
            background-color: white;
        }}
        .status-banner {{
            background-color: {status_color};
            color: white !important;
            padding: 20px;
            border-radius: 6px;
            text-align: center;
            margin-bottom: 30px;
        }}
        .status-banner h2 {{
            margin: 0;
            font-size: 20px;
            color: white !important;
        }}
        .status-banner div {{
            color: white !important;
        }}
        .stats-grid {{
            display: -webkit-box;
            display: -webkit-flex;
            display: -moz-box;
            display: -ms-flexbox;
            display: flex;
            -webkit-flex-wrap: wrap;
            -ms-flex-wrap: wrap;
            flex-wrap: wrap;
            -webkit-box-pack: center;
            -webkit-justify-content: center;
            -moz-box-pack: center;
            -ms-flex-pack: center;
            justify-content: center;
            margin-bottom: 30px;
            gap: 15px;
        }}
        
        /* Table fallback for email clients that don't support flexbox */
        @media screen and (max-width: 480px) {{
            .stats-grid {{
                display: block !important;
            }}
            .stat-card {{
                display: block !important;
                width: 100% !important;
                margin: 10px 0 !important;
            }}
        }}
        
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            text-align: center;
            border: 1px solid #e9ecef;
            -webkit-box-flex: 0;
            -webkit-flex: 0 0 160px;
            -moz-box-flex: 0;
            -ms-flex: 0 0 160px;
            flex: 0 0 160px;
            min-width: 160px;
            max-width: 160px;
            margin: 5px;
        }}
        .stat-number {{
            font-size: 28px;
            font-weight: bold;
            color: #1da1f2;
            display: block;
        }}
        .stat-label {{
            color: #6c757d;
            font-size: 14px;
            margin-top: 5px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h3 {{
            color: #495057;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 8px;
            margin-bottom: 20px;
        }}
        .account-list {{
            background: #f8f9fa;
            border-radius: 6px;
            padding: 20px;
            border: 1px solid #e9ecef;
        }}
        .account-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #e9ecef;
        }}
        .account-item:last-child {{
            border-bottom: none;
        }}
        .account-name {{
            font-weight: 600;
            color: #495057;
        }}
        .account-stats {{
            font-size: 14px;
            color: #6c757d;
        }}
        .success {{ 
            color: #28a745 !important;
            font-weight: bold;
        }}
        .error {{ 
            color: #dc3545 !important;
            font-weight: bold;
        }}
        .warning {{ 
            color: #ffc107 !important;
            font-weight: bold;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #6c757d;
            border-top: 1px solid #e9ecef;
        }}
        .details-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            border: 1px solid #e9ecef;
        }}
        .details-table th, .details-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }}
        .details-table th {{
            background-color: #f8f9fa;
            font-weight: 600;
            color: #495057;
        }}
        .details-table td {{
            color: #495057;
        }}
        
        /* Force important colors that should remain visible in dark mode */
        .success-text {{
            color: #28a745 !important;
        }}
        .error-text {{
            color: #dc3545 !important;
        }}
        .warning-text {{
            color: #fd7e14 !important;
        }}
        
        /* High contrast text for dark mode */
        @media (prefers-color-scheme: dark) {{
            .account-name {{
                color: #ffffff !important;
            }}
            .account-stats {{
                color: #cccccc !important;
            }}
            .section h3 {{
                color: #ffffff !important;
            }}
            .stat-label {{
                color: #cccccc !important;
            }}
            .details-table th {{
                color: #ffffff !important;
            }}
            .details-table td {{
                color: #cccccc !important;
            }}
            .footer {{
                color: #cccccc !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐦 Twitter Approval Automation Results</h1>
            <div class="subtitle">Batch ID: {batch_id} | {execution_mode} Mode</div>
        </div>
        
        <div class="content">
            <div class="status-banner">
                <h2>{status_emoji} Automation Status: {status_text}</h2>
                <div>Success Rate: {stats['success_rate']}% ({stats['successful_accounts']}/{stats['total_accounts']} accounts)</div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <span class="stat-number">{stats['total_accounts']}</span>
                    <div class="stat-label">Total Accounts</div>
                </div>
                <div class="stat-card">
                    <span class="stat-number success-text">{stats['successful_accounts']}</span>
                    <div class="stat-label">Successful</div>
                </div>
                <div class="stat-card">
                    <span class="stat-number error-text">{stats['failed_accounts']}</span>
                    <div class="stat-label">Failed</div>
                </div>
                <div class="stat-card">
                    <span class="stat-number">{stats['total_approvals']}</span>
                    <div class="stat-label">Total Approvals</div>
                </div>
            </div>
        '''
        
        # Failed Accounts Section
        if stats['failed_accounts_details']:
            html_content += '''
            <div class="section">
                <h3>❌ Failed Accounts</h3>
                <div class="account-list">
            '''
            for account in stats['failed_accounts_details']:
                username = account.get('username', 'Unknown')
                error = account.get('error', 'Unknown error')
                duration = self._format_duration(account.get('duration', 0))
                html_content += f'''
                    <div class="account-item">
                        <div>
                            <div class="account-name">@{username}</div>
                            <div class="account-stats error-text">{error}</div>
                        </div>
                        <div class="account-stats">{duration}</div>
                    </div>
                '''
            html_content += '</div></div>'
        
        # Authentication Statistics
        auth_stats = stats['auth_stats']
        if auth_stats['total_attempts'] > 0:
            html_content += f'''
            <div class="section">
                <h3>🔐 Authentication Summary</h3>
                <table class="details-table">
                    <tr>
                        <th>Metric</th>
                        <th>Count</th>
                        <th>Percentage</th>
                    </tr>
                    <tr>
                        <td>Total Auth Attempts</td>
                        <td>{auth_stats['total_attempts']}</td>
                        <td>100%</td>
                    </tr>
                    <tr>
                        <td>IMAP Successful</td>
                        <td class="success-text">{auth_stats['imap_successful']}</td>
                        <td class="success-text">{round(auth_stats['imap_successful']/auth_stats['total_attempts']*100, 1) if auth_stats['total_attempts'] > 0 else 0}%</td>
                    </tr>
                    <tr>
                        <td>Manual Fallback</td>
                        <td class="warning-text">{auth_stats['manual_fallback']}</td>
                        <td class="warning-text">{round(auth_stats['manual_fallback']/auth_stats['total_attempts']*100, 1) if auth_stats['total_attempts'] > 0 else 0}%</td>
                    </tr>
                    <tr>
                        <td>Authentication Skipped</td>
                        <td class="error-text">{auth_stats['auth_skipped']}</td>
                        <td class="error-text">{round(auth_stats['auth_skipped']/auth_stats['total_attempts']*100, 1) if auth_stats['total_attempts'] > 0 else 0}%</td>
                    </tr>
                </table>
            </div>
            '''
        
        # Execution Details
        execution_env = results_data.get('execution_environment', execution_mode)
        completion_time = results_data.get('timestamp', timestamp)
        
        success_rate_class = 'success-text' if stats['success_rate'] >= 90 else 'warning-text' if stats['success_rate'] >= 70 else 'error-text'
        
        html_content += f'''
            <div class="section">
                <h3>📊 Execution Details</h3>
                <table class="details-table">
                    <tr>
                        <td><strong>Batch ID:</strong></td>
                        <td>{batch_id}</td>
                    </tr>
                    <tr>
                        <td><strong>Execution Mode:</strong></td>
                        <td>{execution_env}</td>
                    </tr>
                    <tr>
                        <td><strong>Completion Time:</strong></td>
                        <td>{completion_time}</td>
                    </tr>
                    <tr>
                        <td><strong>Success Rate:</strong></td>
                        <td><span class="{success_rate_class}">{stats['success_rate']}%</span></td>
                    </tr>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <div>Twitter Automation System | Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
            <div style="margin-top: 5px;">For questions or issues, contact the development team.</div>
        </div>
    </div>
</body>
</html>
        '''
        
        return html_content
    
    def _create_text_email(self, results_data: Dict, execution_mode: str) -> str:
        """Create plain text email content"""
        stats = self._calculate_stats(results_data)
        timestamp = results_data.get('timestamp', datetime.now(timezone.utc).isoformat())
        batch_id = results_data.get('batch_id', 'Unknown')
        
        # Determine overall status
        if stats['success_rate'] >= 90:
            status_text = "EXCELLENT"
        elif stats['success_rate'] >= 70:
            status_text = "GOOD"
        else:
            status_text = "NEEDS ATTENTION"
        
        text_content = f"""
==========================================
TWITTER APPROVAL AUTOMATION RESULTS
==========================================

Batch ID: {batch_id}
Execution Mode: {execution_mode}
Status: {status_text}
Completion: {timestamp}

==========================================
SUMMARY STATISTICS
==========================================

Total Accounts Processed: {stats['total_accounts']}
Successful Accounts: {stats['successful_accounts']}
Failed Accounts: {stats['failed_accounts']}
Success Rate: {stats['success_rate']}%

Total Follow Requests Approved: {stats['total_approvals']}

==========================================
FAILED ACCOUNTS ({len(stats['failed_accounts_details'])})
==========================================
"""
        
        for account in stats['failed_accounts_details']:
            username = account.get('username', 'Unknown')
            error = account.get('error', 'Unknown error')
            text_content += f"• @{username}: {error}\n"
        
        # Authentication Statistics
        auth_stats = stats['auth_stats']
        if auth_stats['total_attempts'] > 0:
            text_content += f"""
==========================================
AUTHENTICATION SUMMARY
==========================================

Total Authentication Attempts: {auth_stats['total_attempts']}
IMAP Successful: {auth_stats['imap_successful']} ({round(auth_stats['imap_successful']/auth_stats['total_attempts']*100, 1) if auth_stats['total_attempts'] > 0 else 0}%)
Manual Fallback: {auth_stats['manual_fallback']} ({round(auth_stats['manual_fallback']/auth_stats['total_attempts']*100, 1) if auth_stats['total_attempts'] > 0 else 0}%)
Authentication Skipped: {auth_stats['auth_skipped']} ({round(auth_stats['auth_skipped']/auth_stats['total_attempts']*100, 1) if auth_stats['total_attempts'] > 0 else 0}%)
"""
        
        text_content += f"""
==========================================
SYSTEM INFORMATION
==========================================

Execution Environment: {results_data.get('execution_environment', execution_mode)}
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

For questions or issues, contact the development team.
==========================================
"""
        
        return text_content
    
    def send_completion_notification(self, results_data: Dict, execution_mode: str = "UNKNOWN") -> bool:
        """Send automation completion notification"""
        if not self.ses_available:
            print("⚠️ SES not available, skipping email notification")
            return False
        
        if not self.to_emails:
            print("⚠️ No recipient emails configured, skipping email notification")
            return False
        
        try:
            stats = self._calculate_stats(results_data)
            batch_id = results_data.get('batch_id', 'Unknown')
            
            # Create subject line
            if stats['success_rate'] >= 90:
                subject_prefix = "✅ SUCCESS"
            elif stats['success_rate'] >= 70:
                subject_prefix = "⚠️ PARTIAL"
            else:
                subject_prefix = "❌ ISSUES"
            
            subject = f"{subject_prefix} - Twitter Automation Complete | {stats['successful_accounts']}/{stats['total_accounts']} accounts | {stats['total_approvals']} approvals"
            
            # Create email content
            html_body = self._create_html_email(results_data, execution_mode)
            text_body = self._create_text_email(results_data, execution_mode)
            
            # Send email
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={
                    'ToAddresses': self.to_emails
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            
            message_id = response.get('MessageId', 'Unknown')
            print(f"✅ Email notification sent successfully!")
            print(f"   Recipients: {', '.join(self.to_emails)}")
            print(f"   Subject: {subject}")
            print(f"   Message ID: {message_id}")
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"❌ Failed to send email notification: {error_code} - {error_message}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error sending email notification: {str(e)}")
            return False
    
    def send_error_notification(self, error_message: str, execution_mode: str = "UNKNOWN", batch_id: str = "Unknown") -> bool:
        """Send error notification when automation fails completely"""
        if not self.ses_available or not self.to_emails:
            return False
        
        try:
            subject = f"❌ FAILURE - Twitter Automation Error | Batch {batch_id}"
            
            text_body = f"""
TWITTER AUTOMATION ERROR NOTIFICATION

Batch ID: {batch_id}
Execution Mode: {execution_mode}
Error Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

ERROR DETAILS:
{error_message}

Please check the logs for more detailed information.
Contact the development team if this issue persists.
"""
            
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .error-header {{ background-color: #dc3545; color: white; padding: 20px; border-radius: 5px; }}
        .content {{ margin: 20px 0; }}
        .error-details {{ background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="error-header">
        <h2>❌ Twitter Automation Error</h2>
    </div>
    <div class="content">
        <p><strong>Batch ID:</strong> {batch_id}</p>
        <p><strong>Execution Mode:</strong> {execution_mode}</p>
        <p><strong>Error Time:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        
        <div class="error-details">
            <h3>Error Details:</h3>
            <pre>{error_message}</pre>
        </div>
        
        <p>Please check the logs for more detailed information.<br>
        Contact the development team if this issue persists.</p>
    </div>
</body>
</html>
"""
            
            self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': self.to_emails},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                    }
                }
            )
            
            print(f"✅ Error notification sent to: {', '.join(self.to_emails)}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send error notification: {str(e)}")
            return False

# Test function for the email service
def test_email_service():
    """Test the email service with sample data"""
    print("🧪 Testing Email Service...")
    
    # Create sample results data
    sample_results = {
        'batch_id': 'test-batch-' + datetime.now().strftime('%Y%m%d-%H%M%S'),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'execution_environment': 'LOCAL_TEST',
        'summary': {
            'total_accounts': 3,
            'successful_accounts': 2,
            'failed_accounts': 1,
            'total_approvals': 15,
        },
        'detailed_results': [
            {
                'username': 'test_account_1',
                'success': True,
                'approved_count': 10,
                'followers_saved': 8,
                'duration_seconds': 45.2,
                'auth_code_required': True,
                'auth_method_used': 'imap',
                'error': None
            },
            {
                'username': 'test_account_2', 
                'success': True,
                'approved_count': 5,
                'followers_saved': 4,
                'duration_seconds': 32.1,
                'auth_code_required': False,
                'auth_method_used': None,
                'error': None
            },
            {
                'username': 'test_account_3',
                'success': False,
                'approved_count': 0,
                'followers_saved': 0,
                'duration_seconds': 15.5,
                'auth_code_required': True,
                'auth_method_used': 'skipped',
                'error': 'Authentication required but skipped'
            }
        ]
    }
    
    # Test email service
    email_service = AutomationEmailService()
    success = email_service.send_completion_notification(sample_results, "LOCAL_TEST")
    
    if success:
        print("✅ Test email sent successfully!")
    else:
        print("❌ Test email failed!")
    
    return success

if __name__ == "__main__":
    test_email_service()
