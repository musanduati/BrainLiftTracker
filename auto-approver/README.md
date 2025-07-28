# Twitter Auto Approver

A browser-based automation script to programmatically approve follow requests on Twitter/X for private accounts.

## ⚠️ Important Disclaimer

This tool is for educational and personal use only. Please ensure you comply with:
- Twitter's Terms of Service
- Your local laws and regulations
- Rate limiting to avoid account suspension

Use responsibly and at your own risk.

## 🚀 Quick Start

### Method 1: Bookmarklet (Recommended)

1. **Create a bookmark:**
   - Open your browser's bookmark manager
   - Create a new bookmark
   - Name it "Twitter Auto Approver"
   - Copy the entire content from `bookmarklet.js` and paste it as the URL

2. **Use the bookmark:**
   - Navigate to your Twitter follow requests page
   - Click the bookmark to start auto-approval
   - Click again to stop

### Method 2: Browser Console

1. **Navigate to Twitter:**
   - Go to your Twitter follow requests page
   - URL should be something like: `https://twitter.com/follow_requests`

2. **Open Developer Console:**
   - Press `F12` or `Ctrl+Shift+I` (Windows/Linux)
   - Press `Cmd+Option+I` (Mac)
   - Go to the "Console" tab

3. **Load the script:**
   ```javascript
   // Copy and paste the content of twitter_auto_approver.js
   ```

4. **Start auto-approval:**
   ```javascript
   // Quick start with default settings
   quickStart();
   
   // Or with custom settings
   startAutoApproval({
       delay: 3000,        // 3 seconds between actions
       maxApprovals: 100,  // Maximum 100 approvals
       autoScroll: true    // Auto-scroll for more requests
   });
   ```

## 📁 Files Overview

- **`twitter_auto_approver.js`** - Main automation script
- **`config.js`** - Predefined configurations for different use cases
- **`bookmarklet.js`** - One-click bookmarklet version
- **`README.md`** - This documentation

## ⚙️ Configuration Options

### Basic Configuration
```javascript
{
    delay: 2000,           // Delay between actions (milliseconds)
    maxApprovals: 50,      // Maximum approvals per session
    autoScroll: true       // Automatically scroll to load more requests
}
```

### Predefined Configurations

| Configuration | Delay | Max Approvals | Use Case |
|---------------|-------|---------------|----------|
| `setupDefault()` | 2s | 50 | Safe, moderate speed |
| `setupFast()` | 1s | 100 | Faster processing |
| `setupConservative()` | 5s | 25 | Very safe, slow |
| `setupBulk()` | 1.5s | 200 | Large batches |
| `setupManual()` | 2s | 50 | Manual scrolling required |

## 🎯 How to Use

### Step-by-Step Instructions

1. **Navigate to Follow Requests:**
   - Log into your Twitter account
   - Go to your profile
   - Click on "Followers" 
   - Look for "Follow requests" or similar
   - Or directly visit: `https://twitter.com/follow_requests`

2. **Load the Script:**
   - Open browser console (F12)
   - Copy and paste the script content
   - Or use the bookmarklet

3. **Start Auto-Approval:**
   ```javascript
   // Quick start
   quickStart();
   
   // Or with custom settings
   startAutoApproval({
       delay: 3000,
       maxApprovals: 75
   });
   ```

4. **Monitor Progress:**
   - Watch the console for progress updates
   - The script will show: "✅ Approved follow request #X"
   - Status indicator appears in top-right corner (bookmarklet version)

5. **Stop When Needed:**
   ```javascript
   stopAutoApproval();
   ```

### Available Commands

| Command | Description |
|---------|-------------|
| `quickStart()` | Start with default settings |
| `quickStartFast()` | Start with fast settings |
| `quickStartConservative()` | Start with conservative settings |
| `startAutoApproval(config)` | Start with custom configuration |
| `stopAutoApproval()` | Stop the current process |
| `getApprovalStatus()` | Check current status |

## 🔧 Advanced Usage

### Custom Configuration
```javascript
// Create custom configuration
const customConfig = {
    delay: 1500,           // 1.5 seconds between actions
    maxApprovals: 150,     // Approve up to 150 requests
    autoScroll: true       // Auto-scroll enabled
};

// Start with custom config
startAutoApproval(customConfig);
```

### Manual Control
```javascript
// Create instance without starting
const approver = new TwitterAutoApprover({
    delay: 2000,
    maxApprovals: 50
});

// Start manually
approver.approveRequests();

// Check status
console.log(approver.getStatus());

// Stop manually
approver.stop();
```

## 🛡️ Safety Features

- **Rate Limiting:** Built-in delays between actions
- **Maximum Limits:** Configurable approval limits per session
- **Error Handling:** Graceful error recovery
- **Stop Function:** Easy way to stop the process
- **Page Detection:** Only works on follow requests pages

## 🚨 Troubleshooting

### Common Issues

1. **"Not on Twitter follow requests page"**
   - Make sure you're on the correct page
   - URL should contain `/follow_requests` or similar
   - Try refreshing the page

2. **"No follow request buttons found"**
   - Twitter may have updated their UI
   - Try refreshing the page
   - Check if you have any pending follow requests

3. **Script stops unexpectedly**
   - Check browser console for errors
   - Twitter may have rate-limited your account
   - Try increasing the delay setting

4. **Bookmarklet doesn't work**
   - Make sure you copied the entire code
   - Try the console method instead
   - Check if JavaScript is enabled

### Debug Mode
```javascript
// Enable detailed logging
const approver = new TwitterAutoApprover({
    delay: 2000,
    maxApprovals: 10
});

// Check what buttons are found
const buttons = approver.findFollowRequestButtons();
console.log('Found buttons:', buttons);
```

## 📊 Performance Tips

- **Start Conservative:** Begin with higher delays (3-5 seconds)
- **Monitor Activity:** Watch for any unusual behavior
- **Take Breaks:** Don't run for extended periods
- **Check Limits:** Respect Twitter's rate limits
- **Test First:** Try with small numbers first

## 🔄 Updates and Maintenance

The script is designed to handle Twitter UI changes, but if you encounter issues:

1. Check if Twitter has updated their interface
2. Try refreshing the page and reloading the script
3. Update the selectors in the `findFollowRequestButtons()` method if needed

## 📝 Legal Notice

This tool is provided as-is for educational purposes. Users are responsible for:
- Complying with Twitter's Terms of Service
- Following applicable laws and regulations
- Using the tool responsibly and ethically
- Not violating any platform policies

## 🤝 Contributing

Feel free to improve the script by:
- Adding new selectors for UI changes
- Improving error handling
- Adding new features
- Fixing bugs

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section
2. Review the console for error messages
3. Try different configuration settings
4. Ensure you're on the correct Twitter page

---

**Remember:** Use this tool responsibly and respect Twitter's platform policies! 