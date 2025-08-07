// Twitter Auto Approver Script
// This script automatically approves follow requests on Twitter/X
// Updated to handle popup modal interface

class TwitterAutoApprover {
    constructor(config = {}) {
        this.config = {
            delay: config.delay || 2000, // Delay between actions in ms
            maxApprovals: config.maxApprovals || 50, // Maximum approvals per session
            autoScroll: config.autoScroll !== false, // Whether to auto-scroll for more requests
            allowedUsernames: config.allowedUsernames || [], // List of usernames to auto-approve
            ...config
        };
        
        this.approvedCount = 0;
        this.skippedCount = 0;
        this.isRunning = false;
        this.observer = null;
        this.processedUsernames = new Set(); // Track already processed usernames
        this.noNewRequestsCount = 0; // Track consecutive scrolls with no new requests
    }

    // Wait for a specified amount of time
    async sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Check if we're on the correct Twitter page and if the popup is open
    isOnFollowRequestsPage() {
        const url = window.location.href;
        const isTwitterPage = url.includes('twitter.com') || url.includes('x.com');
        
        // Check for popup modal
        const popupModal = this.findFollowRequestsModal();
        
        return isTwitterPage && popupModal !== null;
    }

    // Find the follow requests popup modal
    findFollowRequestsModal() {
        // Multiple selectors to find the popup modal
        const modalSelectors = [
            '[data-testid="followRequestsModal"]',
            '[data-testid="followerRequestsModal"]',
            '[role="dialog"]',
            '.modal',
            '[aria-modal="true"]',
            'div[style*="position: fixed"]',
            'div[style*="z-index"]'
        ];

        for (const selector of modalSelectors) {
            const modal = document.querySelector(selector);
            if (modal && this.isFollowRequestsModal(modal)) {
                return modal;
            }
        }

        // Fallback: look for modal with "Follower requests" or similar text
        const allModals = document.querySelectorAll('[role="dialog"], .modal, div[style*="position: fixed"]');
        for (const modal of allModals) {
            if (this.isFollowRequestsModal(modal)) {
                return modal;
            }
        }

        return null;
    }

    // Check if a modal contains follow requests
    isFollowRequestsModal(modal) {
        const text = modal.textContent.toLowerCase();
        return text.includes('follower request') || 
               text.includes('follow request') || 
               text.includes('accept') && text.includes('decline');
    }

    // Extract username from a follow request element
    extractUsernameFromRequest(element) {
        // First, find the parent container that contains the whole follow request
        let requestContainer = element;
        let maxLevels = 15;
        
        // Go up to find the container with user info
        while (requestContainer && maxLevels > 0) {
            // Check if this container has UserCell or similar
            if (requestContainer.getAttribute('data-testid')?.includes('UserCell') ||
                requestContainer.querySelector('[data-testid*="UserCell"]')) {
                break;
            }
            requestContainer = requestContainer.parentElement;
            maxLevels--;
        }
        
        if (!requestContainer) {
            requestContainer = element.closest('[data-testid*="UserCell"], [role="button"], div');
        }
        
        // Now search within this container and its parents for username
        let searchElement = requestContainer || element;
        maxLevels = 10;
        
        while (searchElement && maxLevels > 0) {
            // Look for all links that might contain username
            const links = searchElement.querySelectorAll('a[href^="/"]');
            
            for (const link of links) {
                const href = link.getAttribute('href') || '';
                
                // Check if it's a user profile link (format: /username)
                // Exclude links with additional paths like /status, /photo, etc.
                if (href && href.match(/^\/[A-Za-z0-9_]+$/)) {
                    const username = href.substring(1); // Remove leading /
                    // Exclude common non-username paths
                    if (username && 
                        !username.includes(' ') && 
                        username !== 'home' && 
                        username !== 'explore' &&
                        username !== 'notifications' &&
                        username !== 'messages' &&
                        username !== 'settings' &&
                        username !== 'follower_requests') {
                        return username.toLowerCase();
                    }
                }
            }
            
            // Also check for @username in text content
            const spans = searchElement.querySelectorAll('span, div');
            for (const span of spans) {
                const text = span.textContent || '';
                // More specific pattern for @username
                const atMatch = text.match(/@([A-Za-z0-9_]+)(?:\s|$)/);
                if (atMatch) {
                    return atMatch[1].toLowerCase();
                }
            }
            
            searchElement = searchElement.parentElement;
            maxLevels--;
        }
        
        return null;
    }

    // Check if a username is in the allowed list
    isUsernameAllowed(username) {
        // SECURITY: If no filter is set, DENY by default for safety
        if (!this.config.allowedUsernames || this.config.allowedUsernames.length === 0) {
            console.error('❌ SECURITY: No username filter configured - DENYING ALL for safety');
            console.error('To approve requests, you must explicitly provide an allowedUsernames list');
            return false;  // DENY by default when no filter is configured
        }
        
        // Check if username is in the allowed list (case-insensitive)
        const normalizedUsername = username.toLowerCase().trim();
        const normalizedAllowedList = this.config.allowedUsernames.map(u => u.toLowerCase().trim());
        
        const isAllowed = normalizedAllowedList.includes(normalizedUsername);
        
        console.log('=== USERNAME CHECK ===');
        console.log(`Checking: "${username}"`);
        console.log(`Normalized: "${normalizedUsername}"`);
        console.log(`Against list: [${normalizedAllowedList.join(', ')}]`);
        console.log(`Result: ${isAllowed ? '✅ ALLOWED' : '❌ NOT ALLOWED'}`);
        
        // Special warning for known test case
        if (normalizedUsername === 'lim_uncsrd' && isAllowed) {
            console.error('🚨 ERROR: lim_uncsrd should NOT be in allowed list!');
        }
        
        return isAllowed;
    }

    // Find follow request buttons within the modal
    findFollowRequestButtons() {
        const modal = this.findFollowRequestsModal();
        if (!modal) {
            console.log('No follow requests modal found');
            return [];
        }

        // Wait a bit for dynamic content to load
        console.log('Looking for accept buttons in modal...');

        // Multiple selectors to handle different Twitter UI versions
        const selectors = [
            'button[data-testid*="accept"]',
            'button[data-testid*="Accept"]',
            'button[aria-label*="Accept"]',
            'button[aria-label*="Approve"]',
            'div[role="button"][data-testid*="accept"]',
            'div[role="button"][aria-label*="Accept"]',
            // New selectors based on current Twitter UI
            'button[type="button"]',
            'div[role="button"]',
            'span[role="button"]'
        ];

        let buttons = [];
        
        // Try specific selectors first
        for (const selector of selectors) {
            const found = modal.querySelectorAll(selector);
            if (found.length > 0) {
                // Filter for Accept buttons
                const acceptButtons = Array.from(found).filter(button => {
                    const text = button.textContent || '';
                    const ariaLabel = button.getAttribute('aria-label') || '';
                    const lowerText = text.toLowerCase();
                    const lowerAria = ariaLabel.toLowerCase();
                    
                    // Look for Accept button, but not Decline
                    return (lowerText === 'accept' || lowerText.includes('accept') || 
                            lowerAria.includes('accept') || lowerAria.includes('approve')) &&
                           !lowerText.includes('decline') && !lowerAria.includes('decline');
                });
                
                if (acceptButtons.length > 0) {
                    buttons = acceptButtons;
                    console.log(`Found ${buttons.length} accept buttons using selector: ${selector}`);
                    break;
                }
            }
        }

        // Fallback: look for buttons with exact "Accept" text
        if (buttons.length === 0) {
            const allButtons = modal.querySelectorAll('button, div[role="button"], span[role="button"]');
            buttons = Array.from(allButtons).filter(button => {
                const text = (button.textContent || '').trim();
                return text === 'Accept' || text === 'Approve';
            });
            
            if (buttons.length > 0) {
                console.log(`Found ${buttons.length} accept buttons using text matching`);
            }
        }

        // Debug output
        if (buttons.length === 0) {
            console.log('No accept buttons found. All buttons in modal:');
            const allButtons = modal.querySelectorAll('button, div[role="button"], span[role="button"]');
            Array.from(allButtons).slice(0, 10).forEach((btn, i) => {
                console.log(`Button ${i}: "${btn.textContent}" | data-testid="${btn.getAttribute('data-testid')}" | aria-label="${btn.getAttribute('aria-label')}"`);
            });
        }

        console.log(`Total accept buttons found: ${buttons.length}`);
        return buttons;
    }

    // Click a button safely
    async clickButton(button) {
        try {
            // Scroll button into view within the modal
            button.scrollIntoView({ behavior: 'smooth', block: 'center' });
            await this.sleep(500);

            // Try different click methods
            if (button.click) {
                button.click();
            } else if (button.dispatchEvent) {
                button.dispatchEvent(new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));
            }

            return true;
        } catch (error) {
            console.error('Failed to click button:', error);
            return false;
        }
    }

    // Scroll within the modal to load more follow requests
    async scrollForMoreRequests() {
        if (!this.config.autoScroll) return;

        const modal = this.findFollowRequestsModal();
        if (!modal) return;

        // Find scrollable container within the modal
        const scrollableContainer = modal.querySelector('[data-testid="scrollContainer"]') || 
                                   modal.querySelector('.scroll-container') ||
                                   modal;

        if (scrollableContainer) {
            const scrollHeight = scrollableContainer.scrollHeight;
            scrollableContainer.scrollTo(0, scrollHeight);
            await this.sleep(1000);
        }
    }

    // Find all follow request entries with their usernames and buttons
    findFollowRequestEntries() {
        const modal = this.findFollowRequestsModal();
        if (!modal) {
            console.log('No follow requests modal found');
            return [];
        }

        console.log('Looking for follow request entries...');
        
        // First try to find all Accept buttons
        const entries = [];
        const acceptButtons = [];
        
        // Find all potential accept buttons
        const allButtons = modal.querySelectorAll('button');
        for (const button of allButtons) {
            const text = (button.textContent || '').trim();
            
            // Look for "Accept" text specifically (case-sensitive to match Twitter's UI)
            // Skip disabled buttons (already clicked)
            if ((text === 'Accept' || text === 'Approve') && !button.disabled) {
                acceptButtons.push(button);
            }
        }
        
        console.log(`Found ${acceptButtons.length} accept buttons`);
        
        // For each accept button, find its associated username using position-based method
        for (const button of acceptButtons) {
            let username = null;
            
            // Method 1: Find the link on the same row as the button
            const buttonRect = button.getBoundingClientRect();
            const allLinks = modal.querySelectorAll('a[href^="/"]');
            
            let closestLink = null;
            let closestDistance = Infinity;
            
            allLinks.forEach(link => {
                const linkRect = link.getBoundingClientRect();
                const distance = Math.abs(linkRect.top - buttonRect.top);
                if (distance < closestDistance && distance < 100) { // Same row if within 100px
                    closestDistance = distance;
                    closestLink = link;
                }
            });
            
            if (closestLink) {
                const href = closestLink.getAttribute('href') || '';
                if (href.match(/^\/[A-Za-z0-9_]+$/)) {
                    username = href.substring(1); // Remove leading /
                    console.log(`Found username via position: ${username}`);
                }
            }
            
            // Method 2: Fallback - look for @ mentions in parent container
            if (!username) {
                let searchElement = button;
                let attempts = 0;
                
                while (searchElement && attempts < 20) {
                    searchElement = searchElement.parentElement;
                    attempts++;
                    
                    const text = searchElement ? searchElement.textContent : '';
                    if (text && text.includes('@')) {
                        const atMatch = text.match(/@([A-Za-z0-9_]+)/);
                        if (atMatch) {
                            username = atMatch[1];
                            console.log(`Found username via @mention: ${username}`);
                            break;
                        }
                    }
                }
            }
            
            if (username) {
                // Normalize username to lowercase for comparison
                const normalizedUsername = username.toLowerCase();
                entries.push({ 
                    username: normalizedUsername, 
                    button: button
                });
                console.log(`✅ Added entry for @${normalizedUsername}`);
            } else {
                console.warn('⚠️ Could not extract username for this Accept button');
                // Skip entries without username when filter is active
                if (this.config.allowedUsernames && this.config.allowedUsernames.length > 0) {
                    console.log('Skipping due to active filter and no username');
                } else {
                    // SECURITY: Do not add entries without username
                    console.log('❌ Cannot add entry without username - skipping for safety');
                }
            }
        }
        
        console.log(`Total entries: ${entries.length}`);
        console.log('Extracted usernames:', entries.map(e => e.username));
        return entries;
    }

    // Main approval loop
    async approveRequests() {
        if (!this.isOnFollowRequestsPage()) {
            console.error('Not on Twitter follow requests page or modal not open. Please navigate to your follow requests first.');
            return;
        }

        this.isRunning = true;
        console.log('🚀 Starting Twitter Auto Approver (Popup Mode)...');
        if (this.config.allowedUsernames && this.config.allowedUsernames.length > 0) {
            console.log('Username filter active:', this.config.allowedUsernames);
        }

        while (this.isRunning && this.approvedCount < this.config.maxApprovals) {
            const entries = this.findFollowRequestEntries();
            
            // Filter out already processed usernames
            const newEntries = entries.filter(entry => {
                if (!entry.username) return true; // Process entries without username once
                return !this.processedUsernames.has(entry.username);
            });
            
            if (newEntries.length === 0) {
                if (this.config.autoScroll) {
                    this.noNewRequestsCount++;
                    
                    // Stop if we've scrolled 3 times with no new requests
                    if (this.noNewRequestsCount >= 3) {
                        console.log('No new requests found after multiple scrolls. Stopping.');
                        break;
                    }
                    
                    console.log(`No new requests found. Attempting scroll ${this.noNewRequestsCount}/3...`);
                    await this.scrollForMoreRequests();
                    await this.sleep(this.config.delay);
                    
                    // Check if modal is still open
                    if (!this.findFollowRequestsModal()) {
                        console.log('Modal closed. Stopping auto approval.');
                        break;
                    }
                } else {
                    console.log('No more requests to process.');
                    break;
                }
                continue;
            }
            
            // Reset counter since we found new requests
            this.noNewRequestsCount = 0;
            console.log(`Found ${newEntries.length} new request(s) to process`);

            for (const entry of newEntries) {
                if (!this.isRunning || this.approvedCount >= this.config.maxApprovals) {
                    break;
                }

                // Check if modal is still open
                if (!this.findFollowRequestsModal()) {
                    console.log('Modal closed. Stopping auto approval.');
                    this.isRunning = false;
                    break;
                }

                try {
                    const { username, button } = entry;
                    
                    // Mark this username as processed
                    if (username) {
                        this.processedUsernames.add(username);
                    }
                    
                    // Skip if we couldn't extract username and filtering is enabled
                    if (!username) {
                        if (this.config.allowedUsernames && this.config.allowedUsernames.length > 0) {
                            console.warn('Could not extract username - skipping (filter active)');
                            this.skippedCount++;
                            await this.sleep(500);
                            continue;
                        } else {
                            // SECURITY: Never approve without username verification
                            console.warn('❌ Could not extract username - denying for safety');
                            console.warn('Never approve requests without verifying username');
                            this.skippedCount++;
                            await this.sleep(500);
                            continue;
                        }
                    }
                    
                    // SECURITY: Always check username against allow list
                    const isAllowed = this.isUsernameAllowed(username);
                    
                    if (isAllowed) {
                        const success = await this.clickButton(button);
                        if (success) {
                            this.approvedCount++;
                            console.log(`✅ Approved @${username} (#${this.approvedCount})`);
                            await this.sleep(this.config.delay);
                        }
                    } else {
                        this.skippedCount++;
                        console.log(`⏭️ Skipped @${username} (not in allowed list)`);
                        // Small delay before processing next
                        await this.sleep(500);
                    }
                } catch (error) {
                    console.error('Error processing request:', error);
                }
            }

            // Only scroll if we processed all entries and auto-scroll is enabled
            if (this.config.autoScroll && newEntries.length > 0) {
                await this.scrollForMoreRequests();
                await this.sleep(this.config.delay);
            }
        }

        console.log('\n' + '='.repeat(50));
        console.log('🎉 AUTO-APPROVAL COMPLETED');
        console.log('='.repeat(50));
        console.log(`✅ Approved: ${this.approvedCount} requests`);
        console.log(`⏭️  Skipped: ${this.skippedCount} requests`);
        if (this.config.allowedUsernames && this.config.allowedUsernames.length > 0) {
            console.log(`🔒 Filter was active for: ${this.config.allowedUsernames.join(', ')}`);
        }
        console.log('='.repeat(50));
        this.isRunning = false;
    }

    // Stop the approval process
    stop() {
        this.isRunning = false;
        console.log('⏹️ Auto approval stopped.');
    }

    // Get current status
    getStatus() {
        return {
            isRunning: this.isRunning,
            approvedCount: this.approvedCount,
            skippedCount: this.skippedCount,
            maxApprovals: this.config.maxApprovals,
            allowedUsernames: this.config.allowedUsernames
        };
    }
}

// Create global instance
window.twitterAutoApprover = new TwitterAutoApprover();

// Helper functions for easy access
window.startAutoApproval = (config = {}) => {
    // CRITICAL: Ensure config is properly passed
    console.log('Starting auto-approval with config:', config);
    
    // Validate the config
    if (config.allowedUsernames && config.allowedUsernames.length > 0) {
        console.log('🔒 USERNAME FILTER IS ACTIVE');
        console.log('Will ONLY approve:', config.allowedUsernames);
    } else {
        console.error('🚨 SECURITY ERROR: NO USERNAME FILTER PROVIDED!');
        console.error('The auto-approver will DENY ALL requests for safety.');
        console.error('To approve requests, you must provide an allowedUsernames list.');
        const shouldContinue = confirm('No username filter provided. The script will DENY all requests. Continue anyway?');
        if (!shouldContinue) {
            console.log('User cancelled due to missing username filter');
            return null;
        }
    }
    
    window.twitterAutoApprover = new TwitterAutoApprover(config);
    return window.twitterAutoApprover.approveRequests();
};

window.stopAutoApproval = () => {
    if (window.twitterAutoApprover) {
        window.twitterAutoApprover.stop();
    }
};

window.getApprovalStatus = () => {
    if (window.twitterAutoApprover) {
        return window.twitterAutoApprover.getStatus();
    }
    return null;
};

// Auto-start if configured
if (window.location.href.includes('twitter.com') || window.location.href.includes('x.com')) {
    
    console.log('🐦 Twitter Auto Approver loaded! (Popup Mode)');
    console.log('Make sure the follower requests popup is open, then use:');
    console.log('startAutoApproval() to begin, or startAutoApproval({delay: 3000, maxApprovals: 100}) for custom settings');
    console.log('stopAutoApproval() to stop the process');
    console.log('getApprovalStatus() to check current status');
} 