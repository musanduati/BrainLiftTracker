# Twitter Manager Frontend

A modern, beautiful React frontend for managing multiple Twitter accounts, inspired by X Pro's dashboard design.

## Features

- **Account Management**
  - Grid/List view toggle for accounts
  - Account health indicators (token status)
  - Quick actions (refresh token, view tweets, post new tweet)
  - Batch account selection for operations
  - **Twitter Metrics**: Real-time follower/following counts and verified status

- **Account Details Page**
  - Comprehensive account profile with avatar and stats
  - Display of follower and following counts
  - Thread and individual tweet history
  - Performance metrics and activity timeline
  - Content filtering by type (threads, changes)

- **Tweet Management**
  - Twitter-like feed layout
  - Status badges (pending, posted, failed)
  - Inline actions (copy, retry, delete)
  - Batch posting for pending tweets
  - Compose modal with character counter

- **Dark/Light Theme**
  - System-aware theme detection
  - Manual toggle in sidebar
  - Persistent theme preference

- **Responsive Design**
  - Mobile-first approach
  - Collapsible sidebar
  - Adaptive layouts

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- Twitter Manager backend running on `http://localhost:5555`

### Installation

1. Install dependencies:
```bash
npm install
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Update `.env` with your API key:
```
VITE_API_URL=http://localhost:5555/api/v1
VITE_API_KEY=your-api-key-here
```

### Development

Run the development server:

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Build

Build for production:

```bash
npm run build
```

Preview the production build:

```bash
npm run preview
```

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Zustand** for state management
- **React Router v6** for routing
- **Axios** for API calls
- **Lucide React** for icons
- **date-fns** for date formatting
- **react-hot-toast** for notifications
- **@headlessui/react** for accessible UI components
- **framer-motion** for animations

## Project Structure

```
src/
├── components/
│   ├── accounts/       # Account-related components
│   ├── common/         # Reusable UI components
│   ├── layout/         # Layout components (Sidebar, TopBar)
│   └── tweets/         # Tweet-related components
├── pages/              # Page components
├── services/           # API client and services
├── store/             # Zustand store
├── types/             # TypeScript type definitions
└── utils/             # Utility functions
```

## API Integration

The frontend connects to the Flask backend API at `http://localhost:5555/api/v1/`. All API requests require an `X-API-Key` header for authentication.

Key endpoints used:
- `/accounts` - Account management
- `/tweets` - Tweet operations
- `/auth/twitter` - OAuth flow
- `/mock-mode` - Testing mode

## Contributing

1. Follow the existing code style and conventions
2. Use TypeScript for type safety
3. Keep components small and focused
4. Add proper error handling
5. Test on both desktop and mobile views
