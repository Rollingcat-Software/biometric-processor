# Biometric Processor Demo UI

A professional Next.js demo application showcasing the Biometric Processor API capabilities.

## Features

- **Face Enrollment**: Register new faces with quality validation
- **1:1 Verification**: Compare two faces for identity verification
- **1:N Search**: Search for a face across enrolled database
- **Liveness Detection**: Detect presentation attacks
- **Quality Analysis**: Analyze face image quality metrics
- **Demographics Analysis**: Estimate age, gender, and emotions
- **Real-time Proctoring**: Continuous face monitoring with WebSocket
- **Batch Processing**: Process multiple images efficiently

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: TailwindCSS + shadcn/ui
- **State Management**: Zustand
- **Data Fetching**: TanStack Query
- **Testing**: Vitest + Playwright

## Getting Started

### Prerequisites

- Node.js 18.17 or later
- npm 9.0 or later
- Biometric Processor API running on localhost:8001

### Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the demo.

### Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

## Development

```bash
# Run development server
npm run dev

# Run type checking
npm run type-check

# Run linting
npm run lint

# Format code
npm run format

# Run unit tests
npm run test

# Run E2E tests
npm run test:e2e
```

## Project Structure

```
demo-ui/
├── src/
│   ├── app/                 # Next.js App Router pages
│   ├── components/          # React components
│   │   ├── ui/             # shadcn/ui components
│   │   ├── layout/         # Layout components
│   │   ├── media/          # Camera/upload components
│   │   └── biometric/      # Biometric-specific components
│   ├── lib/                # Utilities and core logic
│   │   ├── api/            # API client
│   │   ├── store/          # Zustand stores
│   │   └── utils/          # Utility functions
│   ├── hooks/              # Custom React hooks
│   ├── types/              # TypeScript types
│   └── locales/            # i18n translations
├── tests/                  # Test files
└── public/                 # Static assets
```

## Building for Production

```bash
# Build the application
npm run build

# Start production server
npm run start
```

## License

MIT
