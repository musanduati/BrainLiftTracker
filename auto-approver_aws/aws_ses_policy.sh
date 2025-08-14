#!/bin/bash

# ============================================================================
# AWS SES Setup and Testing Script for Twitter Automation
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    printf "${BLUE}ℹ️  %s${NC}\n" "$1"
}

log_success() {
    printf "${GREEN}✅ %s${NC}\n" "$1"
}

log_warning() {
    printf "${YELLOW}⚠️  %s${NC}\n" "$1"
}

log_error() {
    printf "${RED}❌ %s${NC}\n" "$1"
}

log_step() {
    printf "\n${BLUE}==== %s ====${NC}\n" "$1"
}

# Check AWS credentials
check_aws_credentials() {
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        log_error "AWS CLI is not configured or credentials are invalid."
        log_error "Please run 'aws configure' first."
        exit 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    log_success "AWS credentials validated. Account ID: $ACCOUNT_ID"
}

# Create SES Policy
create_ses_policy() {
    log_step "Creating SES Policy"
    
    # Create the SES permissions policy
    cat > twitter-automation-ses-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail",
                "ses:SendBulkTemplatedEmail",
                "ses:GetSendQuota",
                "ses:GetSendStatistics"
            ],
            "Resource": "*"
        }
    ]
}
EOF

    log_info "SES policy JSON created: twitter-automation-ses-policy.json"
    
    # Create the policy in AWS
    log_info "Creating SES policy in AWS IAM..."
    aws iam create-policy \
        --policy-name TwitterAutomationSESPolicy \
        --policy-document file://twitter-automation-ses-policy.json \
        --description "Allows Twitter automation to send emails via SES" \
        2>/dev/null || log_warning "SES Policy may already exist"
    
    log_success "SES policy created successfully"
}

# Attach SES Policy to existing role
attach_ses_policy() {
    log_step "Attaching SES Policy to ECS Task Role"
    
    # Attach the policy to the existing task role
    aws iam attach-role-policy \
        --role-name ecsTaskRole-twitter \
        --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/TwitterAutomationSESPolicy \
        2>/dev/null || log_warning "SES Policy may already be attached"
    
    log_success "SES policy attached to ecsTaskRole-twitter"
}

# Verify SES setup
verify_ses_setup() {
    log_step "Verifying SES Setup"
    
    # Check SES service availability
    log_info "Checking SES service availability..."
    aws ses get-send-quota --region us-east-1 > /dev/null 2>&1 || {
        log_error "Cannot access SES service. Check your permissions."
        return 1
    }
    
    # Get current SES limits
    log_info "Current SES limits:"
    QUOTA=$(aws ses get-send-quota --region us-east-1)
    echo "$QUOTA" | jq . 2>/dev/null || echo "$QUOTA"
    
    # Check verified email addresses - FIXED COMMAND
    log_info "Checking verified email addresses..."
    VERIFIED_EMAILS=$(aws ses list-identities --region us-east-1 --query 'Identities' --output text)
    
    if echo "$VERIFIED_EMAILS" | grep -q "brainlift.monitor@trilogy.com"; then
        log_success "brainlift.monitor@trilogy.com is verified in SES"
    else
        log_warning "brainlift.monitor@trilogy.com is NOT verified in SES"
        log_info "Please verify this email address in the AWS SES console:"
        log_info "1. Go to AWS SES Console → Verified identities"
        log_info "2. Click 'Create identity' → Email address"
        log_info "3. Enter: brainlift.monitor@trilogy.com"
        log_info "4. Check email and click verification link"
        
        # Show current verified identities
        if [ -n "$VERIFIED_EMAILS" ]; then
            log_info "Currently verified identities:"
            echo "$VERIFIED_EMAILS" | tr '\t' '\n' | sed 's/^/  - /'
        else
            log_info "No verified identities found"
        fi
        return 1
    fi
    
    log_success "SES setup verification completed"
}

# Test SES email sending
test_ses_email() {
    log_step "Testing SES Email Sending"
    
    # Ask for recipient email
    if [ -z "$TEST_EMAIL" ]; then
        echo -n "Enter your email address for testing: "
        read TEST_EMAIL
    fi
    
    if [ -z "$TEST_EMAIL" ]; then
        log_error "No test email provided. Skipping email test."
        return 1
    fi
    
    log_info "Sending test email to: $TEST_EMAIL"
    
    # Create test email content
    SUBJECT="Twitter Automation SES Test - $(date '+%Y-%m-%d %H:%M:%S')"
    BODY="This is a test email from AWS SES for the Twitter Automation system.

Test Details:
- Timestamp: $(date '+%Y-%m-%d %H:%M:%S UTC')
- From: brainlift.monitor@trilogy.com
- AWS Account: $ACCOUNT_ID
- SES Region: us-east-1

If you received this email, SES is properly configured for the Twitter automation system.

Next step: Integrate email notifications into the batch automation process."

    # Send test email
    aws ses send-email \
        --from "brainlift.monitor@trilogy.com" \
        --to "$TEST_EMAIL" \
        --subject "$SUBJECT" \
        --text "$BODY" \
        --region us-east-1 && {
        log_success "Test email sent successfully!"
        log_info "Check your inbox: $TEST_EMAIL"
    } || {
        log_error "Failed to send test email. Check your SES configuration."
        return 1
    }
}

# Test HTML email sending (for future rich notifications)
test_ses_html_email() {
    log_step "Testing SES HTML Email Sending"
    
    if [ -z "$TEST_EMAIL" ]; then
        echo -n "Enter your email address for HTML testing: "
        read TEST_EMAIL
    fi
    
    if [ -z "$TEST_EMAIL" ]; then
        log_warning "No test email provided. Skipping HTML email test."
        return 0
    fi
    
    log_info "Sending HTML test email to: $TEST_EMAIL"
    
    # Create HTML email content
    HTML_BODY='<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #1da1f2; color: white; padding: 20px; border-radius: 5px; }
        .content { margin: 20px 0; }
        .stats { background-color: #f8f9fa; padding: 15px; border-radius: 5px; }
        .success { color: #28a745; }
        .warning { color: #ffc107; }
        .error { color: #dc3545; }
    </style>
</head>
<body>
    <div class="header">
        <h2>🐦 Twitter Automation - SES HTML Test</h2>
    </div>
    
    <div class="content">
        <p>This is a <strong>HTML test email</strong> from AWS SES for the Twitter Automation system.</p>
        
        <div class="stats">
            <h3>Test Configuration:</h3>
            <ul>
                <li><strong>Timestamp:</strong> '$(date '+%Y-%m-%d %H:%M:%S UTC')'</li>
                <li><strong>From:</strong> brainlift.monitor@trilogy.com</li>
                <li><strong>AWS Account:</strong> '$ACCOUNT_ID'</li>
                <li><strong>SES Region:</strong> us-east-1</li>
            </ul>
        </div>
        
        <p class="success">✅ If you received this email, HTML email formatting is working correctly!</p>
        
        <p>Next step: Integrate rich email notifications into the batch automation process.</p>
    </div>
</body>
</html>'

    TEXT_BODY="Twitter Automation SES HTML Test

This is a test of HTML email capabilities.

Test Details:
- Timestamp: $(date '+%Y-%m-%d %H:%M:%S UTC')
- From: brainlift.monitor@trilogy.com
- AWS Account: $ACCOUNT_ID
- SES Region: us-east-1

If you received this email, both text and HTML email are working."

    # Create temporary files for the email content
    echo "$HTML_BODY" > /tmp/test-email.html
    echo "$TEXT_BODY" > /tmp/test-email.txt
    
    # Send HTML email with text fallback
    aws ses send-email \
        --from "brainlift.monitor@trilogy.com" \
        --to "$TEST_EMAIL" \
        --subject "Twitter Automation SES HTML Test - $(date '+%Y-%m-%d %H:%M:%S')" \
        --html "file:///tmp/test-email.html" \
        --text "file:///tmp/test-email.txt" \
        --region us-east-1 && {
        log_success "HTML test email sent successfully!"
        log_info "Check your inbox for formatted email: $TEST_EMAIL"
    } || {
        log_error "Failed to send HTML test email."
        return 1
    }
    
    # Clean up temporary files
    rm -f /tmp/test-email.html /tmp/test-email.txt
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f twitter-automation-ses-policy.json
    rm -f /tmp/test-email.html
    rm -f /tmp/test-email.txt
}

# Main execution
main() {
    log_info "🚀 Starting AWS SES Setup and Testing for Twitter Automation"
    echo
    
    # Check if running setup or just testing
    if [ "$1" = "--test-only" ]; then
        log_info "Running SES tests only (skipping policy creation)"
        check_aws_credentials
        verify_ses_setup
        test_ses_email
        test_ses_html_email
    else
        log_info "Running complete SES setup and testing"
        check_aws_credentials
        create_ses_policy
        attach_ses_policy
        verify_ses_setup
        test_ses_email
        test_ses_html_email
    fi
    
    echo
    log_success "🎉 SES setup and testing completed!"
    log_info "Next steps:"
    log_info "• Verify email addresses in AWS SES console if needed"
    log_info "• Update task definitions with SES environment variables"
    log_info "• Proceed to Phase 2: Email Service Module implementation"
    
    cleanup
}

# Show help
show_help() {
    echo "AWS SES Setup and Testing Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --test-only      Run SES tests only (skip policy creation)"
    echo "  --help          Show this help message"
    echo
    echo "Environment Variables:"
    echo "  TEST_EMAIL      Email address for testing (optional, will prompt if not set)"
    echo
    echo "Examples:"
    echo "  $0                           # Full setup and testing"
    echo "  $0 --test-only              # Test existing SES configuration"
    echo "  TEST_EMAIL=you@domain.com $0 # Set test email via environment"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --test-only)
        main --test-only
        ;;
    *)
        main
        ;;
esac