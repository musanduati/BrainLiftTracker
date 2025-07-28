// Twitter List Follower Script
// This script automatically follows all members in a Twitter list
// Run this in the browser console on a Twitter list members page

class TwitterListFollower {
    constructor(config = {}) {
        this.config = {
            delay: config.delay || 3000, // Delay between follows (milliseconds)
            maxFollows: config.maxFollows || 50, // Maximum follows per session
            autoScroll: config.autoScroll !== false, // Whether to auto-scroll for more members
            ...config
        };
        
        this.followedCount = 0;
        this.isRunning = false;
    }

    // Wait for a specified amount of time
    async sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Check if we're on a Twitter list members page
    isOnListMembersPage() {
        const url = window.location.href;
        return (url.includes('twitter.com') || url.includes('x.com')) && 
               (url.includes('/lists/') && url.includes('/members') ||
                url.includes('/i/lists/') && url.includes('/members'));
    }

    // Find follow buttons for list members
    findFollowButtons() {
        // Multiple selectors to handle different Twitter UI versions
        const selectors = [
            'button[data-testid="follow"]',
            'button[data-testid="unfollow"]',
            'div[data-testid="follow"]',
            'div[data-testid="unfollow"]',
            'button[aria-label*="Follow"]',
            'button[aria-label*="Unfollow"]',
            'div[role="button"][data-testid*="follow"]',
            'div[role="button"][aria-label*="Follow"]'
        ];

        let buttons = [];
        
        // Try specific selectors first
        for (const selector of selectors) {
            const found = document.querySelectorAll(selector);
            if (found.length > 0) {
                buttons = Array.from(found);
                break;
            }
        }

        // Fallback: look for buttons with text content
        if (buttons.length === 0) {
            const allButtons = document.querySelectorAll('button, div[role="button"]');
            buttons = Array.from(allButtons).filter(button => {
                const text = button.textContent.toLowerCase();
                const ariaLabel = button.getAttribute('aria-label') || '';
                return text.includes('follow') && !text.includes('unfollow') ||
                       ariaLabel.includes('follow') && !ariaLabel.includes('unfollow');
            });
        }

        // Filter out already followed users (buttons that say "Following" or "Unfollow")
        buttons = buttons.filter(button => {
            const text = button.textContent.toLowerCase();
            const ariaLabel = button.getAttribute('aria-label') || '';
            return !text.includes('following') && !text.includes('unfollow') &&
                   !ariaLabel.includes('following') && !ariaLabel.includes('unfollow');
        });

        console.log(`Found ${buttons.length} follow buttons`);
        return buttons;
    }

    // Click a follow button safely
    async clickFollowButton(button) {
        try {
            // Scroll button into view
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
            console.error('Failed to click follow button:', error);
            return false;
        }
    }

    // Scroll down to load more list members
    async scrollForMoreMembers() {
        if (!this.config.autoScroll) return;

        const scrollHeight = document.documentElement.scrollHeight;
        window.scrollTo(0, scrollHeight);
        await this.sleep(2000); // Wait longer for content to load
    }

    // Main follow loop
    async followMembers() {
        if (!this.isOnListMembersPage()) {
            console.error('Not on Twitter list members page. Please navigate to a list members page first.');
            return;
        }

        this.isRunning = true;
        console.log('🚀 Starting Twitter List Follower...');

        while (this.isRunning && this.followedCount < this.config.maxFollows) {
            const buttons = this.findFollowButtons();
            
            if (buttons.length === 0) {
                console.log('No more follow buttons found. Scrolling for more...');
                await this.scrollForMoreMembers();
                await this.sleep(this.config.delay);
                continue;
            }

            console.log(`Found ${buttons.length} follow buttons`);

            for (const button of buttons) {
                if (!this.isRunning || this.followedCount >= this.config.maxFollows) {
                    break;
                }

                try {
                    const success = await this.clickFollowButton(button);
                    if (success) {
                        this.followedCount++;
                        console.log(`✅ Followed member #${this.followedCount}`);
                        
                        // Wait for the button to change or disappear
                        await this.sleep(this.config.delay);
                    }
                } catch (error) {
                    console.error('Error following member:', error);
                }
            }

            // Scroll for more members
            await this.scrollForMoreMembers();
            await this.sleep(this.config.delay);
        }

        console.log(`🎉 List following completed! Followed ${this.followedCount} members.`);
        this.isRunning = false;
    }

    // Stop the follow process
    stop() {
        this.isRunning = false;
        console.log('⏹️ List following stopped.');
    }

    // Get current status
    getStatus() {
        return {
            isRunning: this.isRunning,
            followedCount: this.followedCount,
            maxFollows: this.config.maxFollows
        };
    }
}

// Create global instance
window.twitterListFollower = new TwitterListFollower();

// Helper functions for easy access
window.startListFollowing = (config = {}) => {
    window.twitterListFollower = new TwitterListFollower(config);
    return window.twitterListFollower.followMembers();
};

window.stopListFollowing = () => {
    if (window.twitterListFollower) {
        window.twitterListFollower.stop();
    }
};

window.getListFollowingStatus = () => {
    if (window.twitterListFollower) {
        return window.twitterListFollower.getStatus();
    }
    return null;
};

// Quick start functions
window.quickStartListFollowing = () => {
    return startListFollowing();
};

window.quickStartListFollowingFast = () => {
    return startListFollowing({ delay: 1500, maxFollows: 100 });
};

window.quickStartListFollowingConservative = () => {
    return startListFollowing({ delay: 5000, maxFollows: 25 });
};

// Auto-start if configured
if (window.location.href.includes('twitter.com') || window.location.href.includes('x.com')) {
    
    console.log('🐦 Twitter List Follower loaded!');
    console.log('Navigate to a Twitter list members page, then use:');
    console.log('quickStartListFollowing() to begin');
    console.log('startListFollowing({delay: 3000, maxFollows: 100}) for custom settings');
    console.log('stopListFollowing() to stop the process');
    console.log('getListFollowingStatus() to check current status');
} 