# Stock Scanner Application - Quick Start Guide

## 🚀 Getting Started

### Server Access
**Application URL**: http://127.0.0.1:5002
**Status**: ✅ Running
**Environment**: Development Mode with Auto-Reload

---

## 📱 Available Modules

### ✅ Fully Functional Modules

#### 1. Dashboard (`/dashboard` or `/`)
**What it does**: Central hub with portfolio overview
- View Kite connection status
- See total watchlists count
- Track stocks across all watchlists
- Browse available stocks count
- Quick access to recent watchlists
- Quick action buttons

#### 2. Stocks (`/stocks/`)
**What it does**: Browse and search stocks
- **Search**: Type symbol or company name
- **Filters**: Exchange (NSE/BSE), Sector
- **Pagination**: 50 stocks per page
- **Detail View**: Click any stock to see full details
- **Live Quotes**: Real-time prices when Kite connected
- **Add to Watchlist**: From stock detail page

**Pro Tip**: Use the sync button to fetch latest instruments from Kite

#### 3. WatchList (`/watchlist/`)
**What it does**: Manage multiple watchlists
- **Create Watchlists**: Unlimited lists for different strategies
- **Add Stocks**: Search and add with notes
- **Live Updates**: Auto-refresh every 5 seconds
- **Edit Notes**: Track your entry points and targets
- **Remove Stocks**: Easy removal with confirmation

**Pro Tip**: Create separate watchlists for different strategies (e.g., "Day Trading", "Swing Trading", "Long Term")

#### 4. Scanner (`/scanner/`)
**What it does**: Scan stocks by technical criteria
- **10 Pre-configured Scans**:
  - High Volume Breakout
  - Strong Gainers (+3%)
  - Strong Losers (-3%)
  - Volatile Stocks (5%+ movement)
  - Near Day High
  - Near Day Low
  - Gap Up Opening
  - Gap Down Opening
  - Bullish Momentum
  - Bearish Momentum
- **Configurable**: Choose exchange, set result limits
- **Real-time**: Scans live market data

**Pro Tip**: Run scans during market hours for best results

---

### 🚧 Coming Soon Modules

#### 5. Sectors (Placeholder)
Will provide sector-wise analysis and heatmaps

#### 6. Orders (Placeholder)
Will allow placing and managing orders

#### 7. Positions (Placeholder)
Will track your current positions and P&L

#### 8. Backtest (Placeholder)
Will enable strategy backtesting

---

## 🔐 First Time Setup

### Step 1: Register/Login
1. Navigate to http://127.0.0.1:5002
2. Click "Register" if new user
3. Fill in username, email, password
4. Login with credentials

### Step 2: Connect to Kite
1. Go to Settings
2. Enter your Kite API Key and Secret
3. Click "Connect to Kite"
4. Complete OAuth authentication
5. Return to application

**Important**: You need Kite Connect API credentials from Zerodha to use live market data features.

### Step 3: Sync Instruments
1. Go to Stocks page
2. Click "Sync from Kite" button
3. Wait for sync to complete
4. Now you can browse all NSE & BSE stocks

---

## 💡 Key Features

### Real-time Data
- Live stock quotes
- Auto-refresh every 5 seconds
- Real-time scanning
- No page reloads (AJAX)

### Portfolio Management
- Multiple watchlists
- Personal notes for stocks
- Track unlimited stocks
- Color-coded gains/losses

### Stock Scanning
- 10 scanning strategies
- Real-time market data
- Customizable parameters
- Instant results

### Modern UI
- Gradient design
- Smooth animations
- Mobile responsive
- Glassmorphism effects

---

## 🎯 Common Workflows

### Workflow 1: Find and Track a Stock
1. Go to **Stocks** page
2. Search for stock (e.g., "RELIANCE")
3. Click stock to view details
4. Click "Add to Watchlist"
5. Select watchlist and add notes
6. Go to **WatchList** to see live updates

### Workflow 2: Scan for Trading Opportunities
1. Go to **Scanner** page
2. Ensure Kite is connected
3. Select exchange (NSE recommended)
4. Choose a scan preset (e.g., "Strong Gainers")
5. Click "Run Scan"
6. View results with live data
7. Click any stock to see details

### Workflow 3: Monitor Your Watchlist
1. Go to **WatchList** page
2. Click on any watchlist
3. Watch live price updates (auto-refresh)
4. Add more stocks using search
5. Edit notes for each stock
6. Remove stocks as needed

### Workflow 4: Create Multiple Strategy Lists
1. Create "Day Trading" watchlist
2. Create "Swing Trading" watchlist
3. Create "Long Term" watchlist
4. Add relevant stocks to each
5. Monitor all from Dashboard

---

## 🔧 Troubleshooting

### Issue: No stocks showing
**Solution**: Click "Sync from Kite" button on Stocks page

### Issue: Scanner not working
**Solution**: Ensure Kite is connected in Settings

### Issue: No live quotes
**Solution**:
1. Check Kite connection status
2. Verify token hasn't expired
3. Reconnect if needed

### Issue: Page not loading
**Solution**:
1. Check server is running on port 5002
2. Clear browser cache
3. Try incognito/private mode

---

## 📊 Understanding the Data

### Price Display
- **Green**: Stock is gaining (positive change)
- **Red**: Stock is losing (negative change)
- **₹**: Indian Rupee symbol
- **%**: Percentage change from previous close

### Volume Format
- **K**: Thousands (e.g., 50K = 50,000)
- **L**: Lakhs (e.g., 5L = 500,000)
- **Cr**: Crores (e.g., 2Cr = 20,000,000)

### Scanner Criteria
- **High Volume**: More than 1 million shares traded
- **Strong Gainers/Losers**: ±3% or more price change
- **Volatile**: 5%+ difference between high and low
- **Gap Up/Down**: 2%+ difference between open and previous close
- **Near High/Low**: Within 5% of day's high/low

---

## 🎨 UI Elements

### Cards
- **Stat Cards**: Display key metrics with gradients
- **Glass Cards**: Semi-transparent cards with backdrop blur
- **Modern Cards**: Clean cards with shadows

### Buttons
- **Primary (Blue)**: Main actions
- **Success (Green)**: Positive actions
- **Danger (Red)**: Delete/Remove actions
- **Outline**: Secondary actions

### Badges
- **Blue**: Information/Count
- **Green**: Active/Connected
- **Red**: Inactive/Error
- **Yellow**: Warning

---

## ⌨️ Keyboard Tips

- **Tab**: Navigate between form fields
- **Enter**: Submit forms
- **Esc**: Close modals
- **Ctrl/Cmd + F**: Browser search on tables

---

## 📱 Mobile Usage

The application is fully responsive:
- Navigation collapses to hamburger menu
- Tables scroll horizontally
- Cards stack vertically
- Touch-friendly buttons

---

## 🔒 Security Notes

1. **Never share your Kite API credentials**
2. **Logout when done trading**
3. **Use strong passwords**
4. **Keep your access tokens secure**
5. **Don't run on public WiFi**

---

## 📈 Best Practices

### For Day Trading
1. Use Scanner for intraday opportunities
2. Create "Intraday" watchlist
3. Monitor high volume stocks
4. Set alerts (coming soon)

### For Swing Trading
1. Scan for momentum stocks
2. Use notes for entry/exit points
3. Track multiple watchlists
4. Review positions daily

### For Long Term
1. Focus on fundamentals (manual research)
2. Use stocks page for discovery
3. Create sector-wise watchlists
4. Track periodically

---

## 🆘 Need Help?

### Documentation
- Check `PROJECT_STATUS.md` for technical details
- Review `README.md` for setup instructions

### Common Issues
Most issues are related to:
1. Kite connection
2. Expired tokens
3. Missing instrument data
4. Browser cache

### Server Management
```bash
# Start server
cd /Users/codenear/codenear-project-files/Aadhith/V1
source venv/bin/activate
python run.py

# Stop server
Press Ctrl+C in terminal
```

---

## 🎯 Quick Links

- **Dashboard**: http://127.0.0.1:5002/dashboard
- **Stocks**: http://127.0.0.1:5002/stocks/
- **WatchList**: http://127.0.0.1:5002/watchlist/
- **Scanner**: http://127.0.0.1:5002/scanner/
- **Settings**: http://127.0.0.1:5002/settings/
- **Profile**: http://127.0.0.1:5002/profile

---

## 📅 Version Info

**Version**: Phase 1 Complete
**Last Updated**: November 3, 2025
**Status**: 4 of 9 modules functional
**Server**: Running on port 5002

---

## 🚀 What's Next?

Upcoming modules in development:
1. **Sectors** - Sector analysis and heatmaps
2. **Orders** - Order placement and management
3. **Positions** - Position tracking and P&L
4. **Backtest** - Strategy backtesting

---

**Happy Trading!** 📊💹

*Remember: This is a development version. Always verify data from official sources before making trading decisions.*
