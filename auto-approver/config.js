// Twitter Auto Approver Configuration
// Copy and paste this into the browser console to set up different configurations

// Default configuration (safe, moderate speed)
const DEFAULT_CONFIG = {
    delay: 2000,           // 2 seconds between actions
    maxApprovals: 50,      // Maximum 50 approvals per session
    autoScroll: true       // Automatically scroll to load more requests
};

// Fast configuration (use with caution)
const FAST_CONFIG = {
    delay: 1000,           // 1 second between actions
    maxApprovals: 100,     // Maximum 100 approvals per session
    autoScroll: true
};

// Conservative configuration (very safe)
const CONSERVATIVE_CONFIG = {
    delay: 5000,           // 5 seconds between actions
    maxApprovals: 25,      // Maximum 25 approvals per session
    autoScroll: true
};

// Bulk configuration (for large numbers)
const BULK_CONFIG = {
    delay: 1500,           // 1.5 seconds between actions
    maxApprovals: 200,     // Maximum 200 approvals per session
    autoScroll: true
};

// Manual configuration (no auto-scroll)
const MANUAL_CONFIG = {
    delay: 2000,
    maxApprovals: 50,
    autoScroll: false      // You'll need to manually scroll
};

// Quick setup functions
window.setupDefault = () => {
    window.twitterAutoApprover = new TwitterAutoApprover(DEFAULT_CONFIG);
    console.log('✅ Default configuration loaded');
};

window.setupFast = () => {
    window.twitterAutoApprover = new TwitterAutoApprover(FAST_CONFIG);
    console.log('⚡ Fast configuration loaded');
};

window.setupConservative = () => {
    window.twitterAutoApprover = new TwitterAutoApprover(CONSERVATIVE_CONFIG);
    console.log('🛡️ Conservative configuration loaded');
};

window.setupBulk = () => {
    window.twitterAutoApprover = new TwitterAutoApprover(BULK_CONFIG);
    console.log('📦 Bulk configuration loaded');
};

window.setupManual = () => {
    window.twitterAutoApprover = new TwitterAutoApprover(MANUAL_CONFIG);
    console.log('👆 Manual configuration loaded');
};

// Quick start functions
window.quickStart = () => {
    window.setupDefault();
    return window.twitterAutoApprover.approveRequests();
};

window.quickStartFast = () => {
    window.setupFast();
    return window.twitterAutoApprover.approveRequests();
};

window.quickStartConservative = () => {
    window.setupConservative();
    return window.twitterAutoApprover.approveRequests();
};

console.log('🔧 Configuration loaded!');
console.log('Available setups: setupDefault(), setupFast(), setupConservative(), setupBulk(), setupManual()');
console.log('Quick starts: quickStart(), quickStartFast(), quickStartConservative()'); 