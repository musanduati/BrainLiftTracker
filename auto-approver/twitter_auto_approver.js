// Twitter Auto Approver Script
// This script automatically approves follow requests on Twitter/X
// Updated to handle popup modal interface

class TwitterAutoApprover {
    constructor(config = {}) {
        this.config = {
            delay: config.delay || 2000, // Delay between actions in ms
            maxApprovals: config.maxApprovals || 50, // Maximum approvals per session
            autoScroll: config.autoScroll !== false, // Whether to auto-scroll for more requests
            ...config
        };
        
        this.approvedCount = 0;
        this.isRunning = false;
        this.observer = null;
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

    // Main approval loop
    async approveRequests() {
        if (!this.isOnFollowRequestsPage()) {
            console.error('Not on Twitter follow requests page or modal not open. Please navigate to your follow requests first.');
            return;
        }

        this.isRunning = true;
        console.log('🚀 Starting Twitter Auto Approver (Popup Mode)...');

        while (this.isRunning && this.approvedCount < this.config.maxApprovals) {
            const buttons = this.findFollowRequestButtons();
            
            if (buttons.length === 0) {
                console.log('No more follow request buttons found. Scrolling for more...');
                await this.scrollForMoreRequests();
                await this.sleep(this.config.delay);
                
                // Check if modal is still open
                if (!this.findFollowRequestsModal()) {
                    console.log('Modal closed. Stopping auto approval.');
                    break;
                }
                continue;
            }

            console.log(`Found ${buttons.length} follow request buttons`);

            for (const button of buttons) {
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
                    const success = await this.clickButton(button);
                    if (success) {
                        this.approvedCount++;
                        console.log(`✅ Approved follow request #${this.approvedCount}`);
                        
                        // Wait for the button to disappear or change
                        await this.sleep(this.config.delay);
                    }
                } catch (error) {
                    console.error('Error approving request:', error);
                }
            }

            // Scroll for more requests
            await this.scrollForMoreRequests();
            await this.sleep(this.config.delay);
        }

        console.log(`🎉 Auto approval completed! Approved ${this.approvedCount} requests.`);
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
            maxApprovals: this.config.maxApprovals
        };
    }
}

// Create global instance
window.twitterAutoApprover = new TwitterAutoApprover();

// Helper functions for easy access
window.startAutoApproval = (config = {}) => {
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