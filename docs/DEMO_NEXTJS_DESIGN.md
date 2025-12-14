# Biometric Processor Demo - Next.js Professional UI Design Document

**Version:** 1.0.0
**Date:** December 14, 2025
**Status:** Design Complete

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Why Next.js Over Streamlit](#why-nextjs-over-streamlit)
3. [Technology Stack](#technology-stack)
4. [Architecture Overview](#architecture-overview)
5. [Application Structure](#application-structure)
6. [Feature Modules](#feature-modules)
7. [Component Library](#component-library)
8. [API Integration](#api-integration)
9. [Real-Time Features](#real-time-features)
10. [UI/UX Design System](#uiux-design-system)
11. [Software Engineering Compliance](#software-engineering-compliance)
12. [Implementation Plan](#implementation-plan)
13. [Deployment Strategy](#deployment-strategy)

---

## Executive Summary

This document outlines the design for a **professional Next.js demo application** that showcases ALL features of the Biometric Processor v1.0.0. This replaces the Streamlit prototype with a production-grade, enterprise-ready demonstration platform.

### Target Use Cases

| Use Case | Requirements | Next.js Advantage |
|----------|--------------|-------------------|
| **Sales Demos** | Professional polish, impressive animations | Framer Motion, shadcn/ui |
| **Trade Shows** | Mobile/tablet support, offline capable | PWA support, responsive |
| **Technical Evaluations** | Real-time features, WebSocket streaming | Native browser APIs |
| **Training** | Interactive, self-guided | Rich component interactions |
| **Client POCs** | Customizable branding | Tailwind theming |

### Key Design Principles

1. **Enterprise-Grade UI** - shadcn/ui components with professional polish
2. **Full WebRTC Support** - Native camera/video streaming
3. **Real-Time Capable** - WebSocket for proctoring demos
4. **Mobile-First Responsive** - Works on any device
5. **Type-Safe** - Full TypeScript implementation
6. **Testable** - Comprehensive testing with Vitest/Playwright

---

## Why Next.js Over Streamlit

| Aspect | Streamlit | Next.js | Winner |
|--------|-----------|---------|--------|
| **Professional Appearance** | Basic, data-science look | Enterprise polish with shadcn/ui | Next.js |
| **Real-time Webcam** | streamlit-webrtc (clunky) | Native MediaStream API | Next.js |
| **WebSocket Streaming** | Difficult, hacky | Native browser support | Next.js |
| **Mobile Responsiveness** | Poor | Tailwind makes trivial | Next.js |
| **Animations/Transitions** | Limited | Framer Motion | Next.js |
| **Load Time** | Slow (Python server) | Fast (edge/static) | Next.js |
| **SEO/Sharing** | None | Full SSR/SSG support | Next.js |
| **Code Reusability** | Demo only | Can become production app | Next.js |
| **Developer Experience** | Limited tooling | Hot reload, DevTools | Next.js |
| **Rapid Prototyping** | Excellent | Good | Streamlit |

**Decision:** Next.js provides the professional polish required for sales demos and trade shows, with full real-time capabilities for proctoring features.

---

## Technology Stack

### Core Framework

| Component | Technology | Version | Justification |
|-----------|------------|---------|---------------|
| **Framework** | Next.js | 14.x | App Router, Server Components, Edge Runtime |
| **Language** | TypeScript | 5.x | Type safety, better DX |
| **Styling** | TailwindCSS | 3.x | Utility-first, rapid styling |
| **Components** | shadcn/ui | Latest | Beautiful, accessible, customizable |
| **State** | Zustand | 4.x | Lightweight, TypeScript-first |
| **API Client** | TanStack Query | 5.x | Caching, refetching, mutations |

### UI/UX Libraries

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Animations** | Framer Motion | Page transitions, micro-interactions |
| **Charts** | Recharts | Data visualization |
| **Icons** | Lucide React | Consistent iconography |
| **Forms** | React Hook Form + Zod | Validation, type-safe forms |
| **Tables** | TanStack Table | Sortable, filterable data tables |
| **Toasts** | Sonner | Beautiful notifications |

### Real-Time & Media

| Component | Technology | Purpose |
|-----------|------------|---------|
| **WebRTC** | Native API | Camera capture, video streaming |
| **WebSocket** | Native + reconnecting-websocket | Real-time proctoring |
| **Image Processing** | Canvas API | Client-side image manipulation |
| **File Upload** | react-dropzone | Drag-and-drop file handling |

### Development & Testing

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Testing** | Vitest | Unit/Integration tests |
| **E2E Testing** | Playwright | End-to-end testing |
| **Linting** | ESLint + Prettier | Code quality |
| **Type Checking** | TypeScript strict mode | Compile-time safety |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NEXT.JS DEMO APPLICATION                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  PRESENTATION LAYER                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Pages (App Router)                                                   │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │Dashboard│ │Enroll   │ │Verify   │ │Search   │ │Liveness │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │Quality  │ │Demo-    │ │Proctor  │ │Admin    │ │Settings │        │   │
│  │  │Analysis │ │graphics │ │Session  │ │Panel    │ │         │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│  UI COMPONENT LAYER                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  shadcn/ui Base    │  Custom Components     │  Feature Components    │   │
│  │  ─────────────────  ──────────────────────  ─────────────────────── │   │
│  │  Button, Card      │  WebcamCapture         │  SimilarityGauge       │   │
│  │  Dialog, Sheet     │  ImageUploader         │  FaceOverlay           │   │
│  │  Table, Form       │  ResultDisplay         │  LivenessChallenge     │   │
│  │  Tabs, Accordion   │  MetricsCard           │  ProctoringFeed        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│  STATE & DATA LAYER                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │  Zustand Store │  │ TanStack Query │  │  WebSocket     │                 │
│  │  ────────────  │  │ ────────────── │  │  Manager       │                 │
│  │  • UI State    │  │  • API Cache   │  │  • Connection  │                 │
│  │  • Settings    │  │  • Mutations   │  │  • Events      │                 │
│  │  • Theme       │  │  • Prefetch    │  │  • Reconnect   │                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  API INTEGRATION LAYER                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  TypeScript API Client (Type-safe, Auto-generated from OpenAPI)       │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │ /faces/*    │ │ /liveness/* │ │ /proctoring │ │ /admin/*    │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│                      BIOMETRIC PROCESSOR API (localhost:8001)                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility | Key Patterns |
|-------|---------------|--------------|
| **Presentation** | Page routing, layout, composition | App Router, Layouts |
| **UI Component** | Reusable visual components | Compound Components, Composition |
| **State & Data** | Application state, server cache | Observer, Cache-Aside |
| **API Integration** | HTTP/WebSocket communication | Repository, Adapter |

---

## Application Structure

```
biometric-processor/demo-ui/
├── src/
│   ├── app/                              # Next.js App Router
│   │   ├── layout.tsx                    # Root layout with providers
│   │   ├── page.tsx                      # Dashboard/Welcome
│   │   ├── globals.css                   # Global styles
│   │   ├── (features)/                   # Feature route group
│   │   │   ├── enrollment/
│   │   │   │   └── page.tsx              # Face Enrollment
│   │   │   ├── verification/
│   │   │   │   └── page.tsx              # 1:1 Verification
│   │   │   ├── search/
│   │   │   │   └── page.tsx              # 1:N Search
│   │   │   ├── liveness/
│   │   │   │   └── page.tsx              # Liveness Detection
│   │   │   ├── quality/
│   │   │   │   └── page.tsx              # Quality Analysis
│   │   │   ├── demographics/
│   │   │   │   └── page.tsx              # Demographics Analysis
│   │   │   ├── landmarks/
│   │   │   │   └── page.tsx              # Facial Landmarks
│   │   │   ├── comparison/
│   │   │   │   └── page.tsx              # Face Comparison
│   │   │   └── batch/
│   │   │       └── page.tsx              # Batch Processing
│   │   ├── (proctoring)/                 # Proctoring route group
│   │   │   ├── session/
│   │   │   │   └── page.tsx              # Proctoring Session
│   │   │   └── realtime/
│   │   │       └── page.tsx              # Real-time Feed
│   │   ├── (admin)/                      # Admin route group
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx              # Admin Dashboard
│   │   │   ├── webhooks/
│   │   │   │   └── page.tsx              # Webhook Management
│   │   │   ├── config/
│   │   │   │   └── page.tsx              # Configuration
│   │   │   └── api-explorer/
│   │   │       └── page.tsx              # Interactive API Testing
│   │   └── settings/
│   │       └── page.tsx                  # App Settings
│   │
│   ├── components/                       # React Components
│   │   ├── ui/                           # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── form.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   └── ...
│   │   ├── layout/                       # Layout components
│   │   │   ├── header.tsx                # App header
│   │   │   ├── sidebar.tsx               # Navigation sidebar
│   │   │   ├── footer.tsx                # App footer
│   │   │   └── page-container.tsx        # Page wrapper
│   │   ├── media/                        # Media components
│   │   │   ├── webcam-capture.tsx        # WebRTC camera
│   │   │   ├── image-uploader.tsx        # Drag-drop upload
│   │   │   ├── image-preview.tsx         # Image display
│   │   │   └── video-stream.tsx          # WebSocket video
│   │   ├── biometric/                    # Biometric-specific
│   │   │   ├── face-overlay.tsx          # Face bounding box
│   │   │   ├── similarity-gauge.tsx      # Radial gauge
│   │   │   ├── quality-meter.tsx         # Quality visualization
│   │   │   ├── liveness-challenge.tsx    # Challenge UI
│   │   │   ├── landmark-viewer.tsx       # 468-point display
│   │   │   └── embedding-visual.tsx      # Embedding heatmap
│   │   ├── charts/                       # Data visualization
│   │   │   ├── similarity-chart.tsx      # Bar/radar charts
│   │   │   ├── metrics-chart.tsx         # Performance metrics
│   │   │   └── timeline-chart.tsx        # Event timeline
│   │   └── common/                       # Shared components
│   │       ├── loading-spinner.tsx
│   │       ├── error-boundary.tsx
│   │       ├── result-card.tsx
│   │       ├── json-viewer.tsx
│   │       └── metrics-card.tsx
│   │
│   ├── lib/                              # Utilities & Core Logic
│   │   ├── api/                          # API Client
│   │   │   ├── client.ts                 # Base HTTP client
│   │   │   ├── endpoints.ts              # API endpoint definitions
│   │   │   ├── types.ts                  # API response types
│   │   │   └── hooks.ts                  # TanStack Query hooks
│   │   ├── websocket/                    # WebSocket Client
│   │   │   ├── manager.ts                # Connection manager
│   │   │   ├── events.ts                 # Event type definitions
│   │   │   └── hooks.ts                  # React hooks
│   │   ├── media/                        # Media Utilities
│   │   │   ├── camera.ts                 # Camera access
│   │   │   ├── image-processing.ts       # Canvas operations
│   │   │   └── file-utils.ts             # File handling
│   │   ├── store/                        # Zustand Stores
│   │   │   ├── app-store.ts              # Global app state
│   │   │   ├── settings-store.ts         # User preferences
│   │   │   └── proctoring-store.ts       # Proctoring session
│   │   └── utils/                        # General Utilities
│   │       ├── cn.ts                     # Class name merge
│   │       ├── format.ts                 # Data formatting
│   │       └── validation.ts             # Input validation
│   │
│   ├── hooks/                            # Custom React Hooks
│   │   ├── use-webcam.ts                 # Camera hook
│   │   ├── use-websocket.ts              # WebSocket hook
│   │   ├── use-api-health.ts             # Health check hook
│   │   └── use-media-query.ts            # Responsive hook
│   │
│   └── types/                            # TypeScript Types
│       ├── api.ts                        # API types
│       ├── biometric.ts                  # Domain types
│       └── proctoring.ts                 # Proctoring types
│
├── public/                               # Static Assets
│   ├── images/
│   │   └── sample-faces/                 # Demo face images
│   └── icons/
│
├── tests/                                # Test Files
│   ├── unit/                             # Vitest unit tests
│   ├── integration/                      # Integration tests
│   └── e2e/                              # Playwright E2E tests
│
├── .env.local                            # Environment variables
├── .env.example                          # Environment template
├── next.config.js                        # Next.js configuration
├── tailwind.config.ts                    # Tailwind configuration
├── tsconfig.json                         # TypeScript configuration
├── vitest.config.ts                      # Vitest configuration
├── playwright.config.ts                  # Playwright configuration
├── components.json                       # shadcn/ui configuration
└── package.json                          # Dependencies
```

---

## Feature Modules

### Phase 1: Core Biometrics

| Page | Route | Features |
|------|-------|----------|
| **Dashboard** | `/` | Feature overview, API health, quick stats, navigation cards |
| **Face Enrollment** | `/enrollment` | Webcam capture, file upload, quality validation, duplicate check |
| **Face Verification** | `/verification` | 1:1 matching, similarity gauge, side-by-side comparison |
| **Face Search** | `/search` | 1:N identification, ranked results, threshold filtering |
| **Liveness Detection** | `/liveness` | Passive/active modes, challenge-response, spoof detection |

### Phase 2: Advanced Analysis

| Page | Route | Features |
|------|-------|----------|
| **Quality Analysis** | `/quality` | Multi-factor quality scoring, improvement suggestions |
| **Demographics** | `/demographics` | Age, gender, emotion detection with confidence |
| **Facial Landmarks** | `/landmarks` | 468-point visualization, interactive canvas |
| **Face Comparison** | `/comparison` | Direct image-to-image comparison |
| **Batch Processing** | `/batch` | Multi-file processing, progress tracking, export |

### Phase 3: Proctoring Suite

| Page | Route | Features |
|------|-------|----------|
| **Proctoring Session** | `/session` | Full session management, real-time analysis |
| **Real-time Feed** | `/realtime` | WebSocket video streaming, live detection |

### Phase 4: Administration

| Page | Route | Features |
|------|-------|----------|
| **Admin Dashboard** | `/admin/dashboard` | System metrics, enrollment stats |
| **Webhooks** | `/admin/webhooks` | Event subscription management |
| **Configuration** | `/admin/config` | System configuration viewer |
| **API Explorer** | `/admin/api-explorer` | Interactive API testing (like Swagger) |

---

## Component Library

### Base Components (shadcn/ui)

```typescript
// Components to install from shadcn/ui
const shadcnComponents = [
  'button',
  'card',
  'dialog',
  'dropdown-menu',
  'form',
  'input',
  'label',
  'select',
  'slider',
  'switch',
  'table',
  'tabs',
  'toast',
  'tooltip',
  'progress',
  'skeleton',
  'separator',
  'badge',
  'alert',
  'avatar',
  'sheet',
  'accordion',
];
```

### Custom Components

#### WebcamCapture Component

```typescript
interface WebcamCaptureProps {
  onCapture: (imageData: string) => void;
  onError?: (error: Error) => void;
  aspectRatio?: '1:1' | '4:3' | '16:9';
  showOverlay?: boolean;
  overlayType?: 'oval' | 'rectangle' | 'none';
  resolution?: 'hd' | 'fhd' | '4k';
  facingMode?: 'user' | 'environment';
  mirrored?: boolean;
}
```

#### SimilarityGauge Component

```typescript
interface SimilarityGaugeProps {
  value: number;              // 0-1 similarity score
  threshold?: number;         // Match threshold (default 0.6)
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  animated?: boolean;
  colorScheme?: 'default' | 'gradient';
}
```

#### ImageUploader Component

```typescript
interface ImageUploaderProps {
  onUpload: (file: File) => void;
  accept?: string[];          // ['image/jpeg', 'image/png']
  maxSize?: number;           // Max file size in bytes
  preview?: boolean;
  multiple?: boolean;
  dropzoneText?: string;
}
```

---

## API Integration

### Type-Safe API Client

```typescript
// lib/api/client.ts
import { QueryClient } from '@tanstack/react-query';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

class BiometricAPIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  // Face Operations
  async enrollFace(params: EnrollFaceParams): Promise<EnrollFaceResponse> { ... }
  async verifyFace(params: VerifyFaceParams): Promise<VerifyFaceResponse> { ... }
  async searchFace(params: SearchFaceParams): Promise<SearchFaceResponse> { ... }
  async deleteFace(userId: string): Promise<void> { ... }

  // Liveness
  async checkLiveness(params: LivenessParams): Promise<LivenessResponse> { ... }

  // Analysis
  async analyzeQuality(image: File): Promise<QualityResponse> { ... }
  async detectDemographics(image: File): Promise<DemographicsResponse> { ... }
  async detectLandmarks(image: File): Promise<LandmarksResponse> { ... }

  // Admin
  async getHealth(): Promise<HealthResponse> { ... }
  async getMetrics(): Promise<MetricsResponse> { ... }
}

export const apiClient = new BiometricAPIClient();
```

### TanStack Query Hooks

```typescript
// lib/api/hooks.ts
export function useEnrollFace() {
  return useMutation({
    mutationFn: (params: EnrollFaceParams) => apiClient.enrollFace(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['faces'] });
    },
  });
}

export function useVerifyFace() {
  return useMutation({
    mutationFn: (params: VerifyFaceParams) => apiClient.verifyFace(params),
  });
}

export function useApiHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.getHealth(),
    refetchInterval: 30000, // Check every 30 seconds
  });
}
```

---

## Real-Time Features

### WebSocket Manager

```typescript
// lib/websocket/manager.ts
class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  connect(sessionId: string): void {
    const url = `${WS_BASE}/proctoring/${sessionId}/stream`;
    this.ws = new WebSocket(url);

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.emit(data.type, data.payload);
    };

    this.ws.onclose = () => this.handleReconnect(sessionId);
  }

  subscribe(event: string, callback: (data: any) => void): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);

    return () => this.listeners.get(event)?.delete(callback);
  }

  send(type: string, payload: any): void {
    this.ws?.send(JSON.stringify({ type, payload }));
  }
}
```

### Proctoring Session Hook

```typescript
// hooks/use-proctoring-session.ts
export function useProctoringSession(sessionId: string) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'error'>('connecting');
  const [events, setEvents] = useState<ProctoringEvent[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    const ws = new WebSocketManager();
    ws.connect(sessionId);

    ws.subscribe('face_detected', (data) => {
      setEvents((prev) => [...prev, { type: 'face', ...data }]);
    });

    ws.subscribe('alert', (data) => {
      setAlerts((prev) => [...prev, data]);
    });

    return () => ws.disconnect();
  }, [sessionId]);

  return { status, events, alerts };
}
```

---

## UI/UX Design System

This section defines a comprehensive, professional design system ensuring consistency, accessibility, and optimal user experience across all demo pages.

---

### Design Principles

| Principle | Description | Implementation |
|-----------|-------------|----------------|
| **Clarity** | Users understand what's happening | Clear labels, visible feedback, progressive disclosure |
| **Efficiency** | Minimize steps to complete tasks | Smart defaults, keyboard shortcuts, batch operations |
| **Forgiveness** | Easy to recover from errors | Undo actions, confirmation dialogs, clear error messages |
| **Feedback** | System responds to every action | Loading states, success/error toasts, progress indicators |
| **Consistency** | Same patterns everywhere | Unified component library, standard interactions |
| **Accessibility** | Usable by everyone | WCAG 2.1 AA compliance, keyboard navigation, screen readers |

---

### Color System

#### Complete Color Palette

```typescript
// tailwind.config.ts
const colors = {
  // Primary - Blue for trust/security (biometric context)
  primary: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',   // Default
    600: '#2563eb',   // Hover
    700: '#1d4ed8',   // Active
    800: '#1e40af',
    900: '#1e3a8a',
    950: '#172554',
  },

  // Neutral - Gray scale for text and backgrounds
  neutral: {
    50: '#fafafa',    // Page background (light)
    100: '#f4f4f5',   // Card background
    200: '#e4e4e7',   // Borders
    300: '#d4d4d8',   // Disabled
    400: '#a1a1aa',   // Placeholder text
    500: '#71717a',   // Secondary text
    600: '#52525b',   // Primary text
    700: '#3f3f46',   // Headings
    800: '#27272a',   // Card background (dark)
    900: '#18181b',   // Page background (dark)
    950: '#09090b',
  },

  // Success - Green for matches and positive outcomes
  success: {
    50: '#f0fdf4',
    100: '#dcfce7',
    200: '#bbf7d0',
    500: '#22c55e',   // Default
    600: '#16a34a',   // Hover
    700: '#15803d',   // Active
  },

  // Warning - Amber for thresholds and caution
  warning: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    500: '#f59e0b',   // Default
    600: '#d97706',   // Hover
    700: '#b45309',   // Active
  },

  // Danger - Red for failures and destructive actions
  danger: {
    50: '#fef2f2',
    100: '#fee2e2',
    200: '#fecaca',
    500: '#ef4444',   // Default
    600: '#dc2626',   // Hover
    700: '#b91c1c',   // Active
  },

  // Info - Cyan for informational messages
  info: {
    50: '#ecfeff',
    100: '#cffafe',
    500: '#06b6d4',
    600: '#0891b2',
  },
};
```

#### Color Contrast Ratios (WCAG 2.1 AA)

| Combination | Ratio | Usage |
|-------------|-------|-------|
| neutral-700 on neutral-50 | 10.5:1 | Body text on light bg |
| neutral-50 on primary-600 | 8.6:1 | Button text |
| neutral-50 on danger-600 | 7.2:1 | Error button text |
| primary-600 on neutral-50 | 4.8:1 | Links on light bg |
| neutral-400 on neutral-50 | 3.5:1 | Placeholder (passes AA large) |

#### Semantic Color Usage

| Context | Light Mode | Dark Mode |
|---------|------------|-----------|
| **Page Background** | neutral-50 | neutral-900 |
| **Card Background** | white | neutral-800 |
| **Primary Text** | neutral-700 | neutral-100 |
| **Secondary Text** | neutral-500 | neutral-400 |
| **Border** | neutral-200 | neutral-700 |
| **Focus Ring** | primary-500 | primary-400 |
| **Match Found** | success-500 | success-400 |
| **No Match** | danger-500 | danger-400 |
| **Low Quality** | warning-500 | warning-400 |

---

### Typography Scale

```typescript
// Typography system based on 16px base
const typography = {
  // Font families
  fontFamily: {
    sans: ['Inter', 'system-ui', 'sans-serif'],
    mono: ['JetBrains Mono', 'Consolas', 'monospace'],
  },

  // Type scale (rem units)
  fontSize: {
    'xs':   ['0.75rem', { lineHeight: '1rem' }],      // 12px - Captions
    'sm':   ['0.875rem', { lineHeight: '1.25rem' }],  // 14px - Small text
    'base': ['1rem', { lineHeight: '1.5rem' }],       // 16px - Body
    'lg':   ['1.125rem', { lineHeight: '1.75rem' }],  // 18px - Lead text
    'xl':   ['1.25rem', { lineHeight: '1.75rem' }],   // 20px - H4
    '2xl':  ['1.5rem', { lineHeight: '2rem' }],       // 24px - H3
    '3xl':  ['1.875rem', { lineHeight: '2.25rem' }],  // 30px - H2
    '4xl':  ['2.25rem', { lineHeight: '2.5rem' }],    // 36px - H1
    '5xl':  ['3rem', { lineHeight: '1' }],            // 48px - Display
  },

  // Font weights
  fontWeight: {
    normal: '400',   // Body text
    medium: '500',   // Emphasis, buttons
    semibold: '600', // Subheadings
    bold: '700',     // Headings
  },
};
```

#### Typography Usage

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| **Page Title** | 4xl (36px) | bold | neutral-900 |
| **Section Title** | 2xl (24px) | semibold | neutral-800 |
| **Card Title** | xl (20px) | semibold | neutral-700 |
| **Body Text** | base (16px) | normal | neutral-600 |
| **Small/Caption** | sm (14px) | normal | neutral-500 |
| **Label** | sm (14px) | medium | neutral-700 |
| **Button** | sm (14px) | medium | varies |
| **Code/Data** | sm (14px) | normal | mono font |

---

### Spacing System

```typescript
// 4px base unit spacing scale
const spacing = {
  px: '1px',
  0: '0',
  0.5: '0.125rem',  // 2px
  1: '0.25rem',     // 4px
  1.5: '0.375rem',  // 6px
  2: '0.5rem',      // 8px
  2.5: '0.625rem',  // 10px
  3: '0.75rem',     // 12px
  4: '1rem',        // 16px - Base unit
  5: '1.25rem',     // 20px
  6: '1.5rem',      // 24px
  8: '2rem',        // 32px
  10: '2.5rem',     // 40px
  12: '3rem',       // 48px
  16: '4rem',       // 64px
  20: '5rem',       // 80px
  24: '6rem',       // 96px
};
```

#### Spacing Usage Guidelines

| Context | Spacing | Example |
|---------|---------|---------|
| **Inline elements** | 1-2 (4-8px) | Icon + text gap |
| **Form field gap** | 3-4 (12-16px) | Label to input |
| **Card padding** | 4-6 (16-24px) | Content padding |
| **Section gap** | 8-12 (32-48px) | Between sections |
| **Page padding** | 4-8 (16-32px) | Responsive margins |

---

### Component States

Every interactive component must define all states:

```typescript
// Button states example
const buttonStates = {
  // Default state
  default: {
    bg: 'primary-500',
    text: 'white',
    border: 'transparent',
  },

  // Hover state (mouse over)
  hover: {
    bg: 'primary-600',
    text: 'white',
    cursor: 'pointer',
    transform: 'translateY(-1px)',
    shadow: 'md',
  },

  // Focus state (keyboard navigation)
  focus: {
    bg: 'primary-500',
    ring: '2px primary-500',
    ringOffset: '2px white',
    outline: 'none',
  },

  // Active state (pressed)
  active: {
    bg: 'primary-700',
    transform: 'translateY(0)',
    shadow: 'none',
  },

  // Disabled state
  disabled: {
    bg: 'neutral-200',
    text: 'neutral-400',
    cursor: 'not-allowed',
    opacity: 0.6,
  },

  // Loading state
  loading: {
    bg: 'primary-400',
    cursor: 'wait',
    content: '<Spinner />',
  },
};
```

#### State Indicators

| State | Visual Indicator |
|-------|------------------|
| **Hover** | Darker bg, slight lift shadow, cursor pointer |
| **Focus** | 2px focus ring with 2px offset |
| **Active** | Darkest bg, pressed effect |
| **Disabled** | Grayed out, 60% opacity, not-allowed cursor |
| **Loading** | Spinner icon, reduced opacity |
| **Error** | Red border, error icon, error message below |
| **Success** | Green checkmark, success message |

---

### Accessibility (WCAG 2.1 AA Compliance)

#### Focus Management

```css
/* Focus ring style - visible on all interactive elements */
.focus-visible {
  outline: none;
  ring: 2px;
  ring-color: primary-500;
  ring-offset: 2px;
}

/* Skip to main content link */
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  padding: 8px 16px;
  background: primary-600;
  color: white;
  z-index: 100;
}
.skip-link:focus {
  top: 0;
}
```

#### Keyboard Navigation

| Key | Action |
|-----|--------|
| `Tab` | Move to next focusable element |
| `Shift+Tab` | Move to previous focusable element |
| `Enter/Space` | Activate button/link |
| `Escape` | Close modal/dropdown |
| `Arrow keys` | Navigate within component (tabs, menus) |
| `Home/End` | Jump to first/last item |

#### Touch Targets

```typescript
// Minimum touch target sizes
const touchTargets = {
  minimum: '44px',      // WCAG minimum
  comfortable: '48px',  // Recommended
  large: '56px',        // Primary actions
};

// Button sizes
const buttonSizes = {
  sm: { height: '32px', padding: '0 12px' },   // Desktop secondary
  md: { height: '40px', padding: '0 16px' },   // Desktop primary
  lg: { height: '48px', padding: '0 24px' },   // Mobile primary (meets touch target)
};
```

#### Screen Reader Support

```tsx
// ARIA labels for biometric components
<WebcamCapture
  aria-label="Camera view for face capture"
  aria-describedby="camera-instructions"
/>
<p id="camera-instructions" className="sr-only">
  Position your face within the oval guide. Ensure good lighting.
</p>

// Live regions for dynamic content
<div aria-live="polite" aria-atomic="true">
  {matchResult && `Match score: ${matchResult.similarity}%`}
</div>

// Progress announcements
<div role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
  Processing image...
</div>
```

#### Color Blind Considerations

| Condition | Accommodation |
|-----------|---------------|
| **Red-Green** | Use icons + text with colors, not color alone |
| **Blue-Yellow** | Avoid blue/yellow only distinctions |
| **Monochromacy** | Ensure sufficient contrast (7:1 for text) |

```tsx
// ✅ GOOD: Color + Icon + Text
<Badge variant="success" icon={<CheckIcon />}>Match Found</Badge>
<Badge variant="error" icon={<XIcon />}>No Match</Badge>

// ❌ BAD: Color only
<div className="bg-green-500" /> // Success
<div className="bg-red-500" />   // Error
```

---

### Responsive Design

#### Breakpoint Behaviors

```typescript
const responsivePatterns = {
  // Mobile (< 640px)
  mobile: {
    sidebar: 'hidden, toggle via hamburger',
    layout: 'single column',
    cards: 'full width, stacked',
    navigation: 'bottom sheet or drawer',
    webcam: 'full width, 4:3 ratio',
    buttons: 'full width, stacked',
    tables: 'card view instead',
  },

  // Tablet (640px - 1024px)
  tablet: {
    sidebar: 'collapsible icons only',
    layout: 'two columns where appropriate',
    cards: '2 per row',
    navigation: 'top bar + icon sidebar',
    webcam: 'centered, max 480px width',
    buttons: 'inline, auto width',
    tables: 'horizontal scroll',
  },

  // Desktop (> 1024px)
  desktop: {
    sidebar: 'expanded with labels',
    layout: 'sidebar + main content',
    cards: '3-4 per row',
    navigation: 'full sidebar',
    webcam: 'sidebar or modal, 400px width',
    buttons: 'inline, fixed width',
    tables: 'full table view',
  },
};
```

#### Mobile-First Component Adaptations

```tsx
// Responsive webcam container
<div className="
  w-full                    // Mobile: full width
  md:w-[480px]              // Tablet: fixed width
  lg:w-[400px]              // Desktop: sidebar width
  aspect-[4/3]              // Consistent aspect ratio
  mx-auto                   // Centered
">
  <WebcamCapture />
</div>

// Responsive button layout
<div className="
  flex flex-col gap-2       // Mobile: stacked
  sm:flex-row sm:gap-4      // Tablet+: inline
">
  <Button className="w-full sm:w-auto">Capture</Button>
  <Button variant="outline" className="w-full sm:w-auto">Cancel</Button>
</div>
```

---

### User Flows

#### Primary User Journey: Face Enrollment

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  1. ENTRY   │────▶│  2. INPUT   │────▶│ 3. CAPTURE  │────▶│  4. REVIEW  │
│  Dashboard  │     │  User ID    │     │   Webcam    │     │   Quality   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                    ┌─────────────┐     ┌─────────────┐            │
                    │  6. DONE    │◀────│  5. SUBMIT  │◀───────────┘
                    │   Success   │     │   Confirm   │
                    └─────────────┘     └─────────────┘
```

| Step | User Action | System Response | Error Path |
|------|-------------|-----------------|------------|
| 1 | Click "Enroll Face" | Navigate to enrollment page | - |
| 2 | Enter User ID | Validate format, check duplicates | Show validation error |
| 3 | Position face, click Capture | Analyze quality in real-time | Show quality feedback |
| 4 | Review captured image | Display quality score, face box | Allow retake if low quality |
| 5 | Click "Confirm Enrollment" | Submit to API, show progress | Show error, allow retry |
| 6 | View success confirmation | Display face ID, quality metrics | - |

#### Error Recovery Flows

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ERROR STATE   │────▶│  EXPLAIN ERROR  │────▶│  OFFER ACTION   │
│   API failed    │     │  "Server busy"  │     │  "Retry" button │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                                               │
         │              ┌─────────────────┐              │
         └─────────────▶│  ALTERNATIVE    │◀─────────────┘
                        │  "Try offline"  │
                        └─────────────────┘
```

---

### Loading States

#### Skeleton Loaders

```tsx
// Page loading skeleton
function PageSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 w-48 bg-neutral-200 rounded mb-4" />
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 bg-neutral-200 rounded" />
        ))}
      </div>
    </div>
  );
}

// Component-level skeleton
function CardSkeleton() {
  return (
    <Card className="animate-pulse">
      <div className="h-4 w-3/4 bg-neutral-200 rounded mb-2" />
      <div className="h-4 w-1/2 bg-neutral-200 rounded" />
    </Card>
  );
}
```

#### Progress Indicators

| Type | Use Case | Visual |
|------|----------|--------|
| **Spinner** | Button loading, quick operations | Rotating circle |
| **Progress Bar** | File upload, known duration | Horizontal bar with % |
| **Skeleton** | Page/component loading | Gray placeholder shapes |
| **Shimmer** | List loading | Moving gradient overlay |
| **Pulse** | Awaiting response | Fading opacity animation |

```tsx
// Biometric processing progress
<div className="space-y-2">
  <Progress value={progress} className="h-2" />
  <div className="flex justify-between text-sm text-neutral-500">
    <span>{stages[currentStage]}</span>
    <span>{progress}%</span>
  </div>
</div>

// Stage indicators
const stages = [
  'Analyzing image quality...',
  'Detecting face...',
  'Extracting features...',
  'Checking for duplicates...',
  'Enrolling face...',
];
```

---

### Empty States

```tsx
// Generic empty state component
interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="text-neutral-300 mb-4">{icon}</div>
      <h3 className="text-lg font-medium text-neutral-700 mb-2">{title}</h3>
      <p className="text-neutral-500 mb-4 max-w-md">{description}</p>
      {action && (
        <Button onClick={action.onClick}>{action.label}</Button>
      )}
    </div>
  );
}

// Usage examples
<EmptyState
  icon={<UserIcon className="w-12 h-12" />}
  title="No faces enrolled"
  description="Start by enrolling a face to enable verification and search features."
  action={{ label: "Enroll First Face", onClick: goToEnrollment }}
/>

<EmptyState
  icon={<SearchIcon className="w-12 h-12" />}
  title="No matches found"
  description="The uploaded face doesn't match any enrolled faces in the database."
/>
```

---

### Error States

```tsx
// Error display component
interface ErrorStateProps {
  type: 'validation' | 'api' | 'biometric' | 'permission';
  message: string;
  details?: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}

function ErrorState({ type, message, details, onRetry, onDismiss }: ErrorStateProps) {
  const icons = {
    validation: <AlertCircleIcon />,
    api: <ServerIcon />,
    biometric: <ScanFaceIcon />,
    permission: <ShieldAlertIcon />,
  };

  return (
    <Alert variant="destructive">
      <div className="flex items-start gap-3">
        {icons[type]}
        <div className="flex-1">
          <AlertTitle>{message}</AlertTitle>
          {details && <AlertDescription>{details}</AlertDescription>}
        </div>
        <div className="flex gap-2">
          {onRetry && (
            <Button size="sm" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          )}
          {onDismiss && (
            <Button size="sm" variant="ghost" onClick={onDismiss}>
              <XIcon className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    </Alert>
  );
}
```

#### Biometric-Specific Errors

| Error | Message | Recovery Action |
|-------|---------|-----------------|
| **No face detected** | "We couldn't detect a face in the image" | "Retake photo with face visible" |
| **Multiple faces** | "Multiple faces detected. Please ensure only one person is visible" | "Retake with single person" |
| **Low quality** | "Image quality is too low (score: 45%)" | "Improve lighting and try again" |
| **Liveness failed** | "Could not verify you're a live person" | "Follow the on-screen prompts" |
| **Duplicate found** | "This face is already enrolled as User X" | "View existing enrollment" |

---

### Notification System (Toasts)

```tsx
// Toast configuration
const toastConfig = {
  position: 'bottom-right',
  duration: {
    success: 3000,
    error: 5000,      // Longer for errors
    warning: 4000,
    info: 3000,
  },
  maxVisible: 3,
};

// Toast variants
<Toast variant="success" icon={<CheckIcon />}>
  Face enrolled successfully
</Toast>

<Toast variant="error" icon={<XIcon />} action={{ label: 'Retry', onClick: retry }}>
  Enrollment failed. Server unavailable.
</Toast>

<Toast variant="warning" icon={<AlertIcon />}>
  Low image quality detected (65%)
</Toast>

<Toast variant="info" icon={<InfoIcon />}>
  Processing may take up to 30 seconds
</Toast>
```

---

### Form Design Patterns

#### Form Layout

```tsx
// Standard form layout
<form className="space-y-6">
  {/* Form section */}
  <div className="space-y-4">
    <h3 className="text-lg font-medium">User Information</h3>

    {/* Form field */}
    <div className="space-y-2">
      <Label htmlFor="userId" className="text-sm font-medium">
        User ID <span className="text-danger-500">*</span>
      </Label>
      <Input
        id="userId"
        placeholder="Enter unique identifier"
        aria-describedby="userId-hint userId-error"
      />
      <p id="userId-hint" className="text-sm text-neutral-500">
        Alphanumeric characters, 3-50 characters
      </p>
      {error && (
        <p id="userId-error" className="text-sm text-danger-500 flex items-center gap-1">
          <AlertCircleIcon className="w-4 h-4" />
          {error}
        </p>
      )}
    </div>
  </div>

  {/* Form actions */}
  <div className="flex justify-end gap-3 pt-4 border-t">
    <Button type="button" variant="outline">Cancel</Button>
    <Button type="submit">Submit</Button>
  </div>
</form>
```

#### Validation Patterns

| Timing | Use Case |
|--------|----------|
| **On blur** | Field validation after user leaves field |
| **On change** | Real-time for format validation (e.g., email) |
| **On submit** | Final validation before API call |
| **Debounced** | Expensive validations (e.g., duplicate check) |

```tsx
// Real-time validation feedback
<Input
  value={userId}
  onChange={handleChange}
  onBlur={handleBlur}
  className={cn(
    'transition-colors',
    error && 'border-danger-500 focus:ring-danger-500',
    valid && 'border-success-500 focus:ring-success-500'
  )}
  rightIcon={
    isValidating ? <Spinner /> :
    valid ? <CheckIcon className="text-success-500" /> :
    error ? <XIcon className="text-danger-500" /> :
    null
  }
/>
```

---

### Biometric-Specific UX

#### Camera UI Design

```tsx
// Face capture overlay component
function FaceCaptureOverlay({ faceDetected, quality, position }) {
  return (
    <div className="relative">
      {/* Video feed */}
      <video className="w-full rounded-lg" />

      {/* Oval guide overlay */}
      <svg className="absolute inset-0 pointer-events-none">
        <defs>
          <mask id="oval-mask">
            <rect width="100%" height="100%" fill="white" />
            <ellipse cx="50%" cy="45%" rx="35%" ry="45%" fill="black" />
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="rgba(0,0,0,0.5)"
          mask="url(#oval-mask)"
        />
        <ellipse
          cx="50%" cy="45%" rx="35%" ry="45%"
          fill="none"
          stroke={faceDetected ? '#22c55e' : '#ef4444'}
          strokeWidth="3"
          strokeDasharray={faceDetected ? 'none' : '10,5'}
        />
      </svg>

      {/* Positioning hints */}
      <div className="absolute bottom-4 left-0 right-0 text-center">
        <Badge variant={faceDetected ? 'success' : 'warning'}>
          {getPositionHint(position)}
        </Badge>
      </div>

      {/* Quality indicator */}
      <div className="absolute top-4 right-4">
        <QualityMeter value={quality} size="sm" />
      </div>
    </div>
  );
}

const getPositionHint = (position) => {
  if (!position.faceDetected) return 'Position your face in the oval';
  if (position.tooClose) return 'Move further from camera';
  if (position.tooFar) return 'Move closer to camera';
  if (position.tooLeft) return 'Move slightly right';
  if (position.tooRight) return 'Move slightly left';
  return 'Perfect! Hold still...';
};
```

#### Similarity Score Visualization

```tsx
// Radial gauge for similarity score
function SimilarityGauge({ score, threshold = 0.6 }) {
  const percentage = Math.round(score * 100);
  const isMatch = score >= threshold;

  const color = isMatch ? 'success' : score >= threshold - 0.1 ? 'warning' : 'danger';

  return (
    <div className="relative w-48 h-48">
      {/* Background circle */}
      <svg className="w-full h-full -rotate-90">
        <circle
          cx="50%" cy="50%" r="45%"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-neutral-200"
        />
        <circle
          cx="50%" cy="50%" r="45%"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeDasharray={`${percentage * 2.83} 283`}
          strokeLinecap="round"
          className={`text-${color}-500 transition-all duration-1000`}
        />
      </svg>

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-4xl font-bold text-${color}-600`}>
          {percentage}%
        </span>
        <span className="text-sm text-neutral-500">
          {isMatch ? 'Match' : 'No Match'}
        </span>
      </div>

      {/* Threshold indicator */}
      <div
        className="absolute w-full h-0.5 bg-neutral-400"
        style={{
          top: '50%',
          transform: `rotate(${(threshold * 360) - 90}deg)`,
          transformOrigin: 'center'
        }}
      />
    </div>
  );
}
```

#### Liveness Challenge UI

```tsx
// Active liveness challenge component
function LivenessChallenge({ challenge, onComplete }) {
  const challenges = {
    blink: {
      instruction: 'Blink your eyes',
      icon: <EyeIcon />,
      animation: 'animate-pulse',
    },
    smile: {
      instruction: 'Smile',
      icon: <SmileIcon />,
      animation: 'animate-bounce',
    },
    turnLeft: {
      instruction: 'Turn your head left',
      icon: <ArrowLeftIcon />,
      animation: 'animate-slide-left',
    },
    turnRight: {
      instruction: 'Turn your head right',
      icon: <ArrowRightIcon />,
      animation: 'animate-slide-right',
    },
  };

  const current = challenges[challenge];

  return (
    <div className="text-center space-y-4">
      <div className={`text-6xl ${current.animation}`}>
        {current.icon}
      </div>
      <p className="text-xl font-medium">{current.instruction}</p>
      <Progress value={progress} className="h-2" />
      <p className="text-sm text-neutral-500">
        Hold for {remainingSeconds} seconds
      </p>
    </div>
  );
}
```

---

### Navigation Design

#### Sidebar Navigation

```tsx
// Responsive sidebar
function Sidebar() {
  return (
    <aside className={cn(
      'fixed left-0 top-0 h-full bg-white border-r',
      'w-64 lg:w-72',                    // Desktop: expanded
      'md:w-16',                          // Tablet: icons only
      'max-md:hidden',                    // Mobile: hidden
    )}>
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b">
        <Logo />
        <span className="ml-3 font-semibold hidden lg:block">
          Biometric Demo
        </span>
      </div>

      {/* Navigation items */}
      <nav className="p-2 space-y-1">
        {navItems.map(item => (
          <NavItem
            key={item.href}
            href={item.href}
            icon={item.icon}
            label={item.label}
            active={pathname === item.href}
          />
        ))}
      </nav>

      {/* API Status */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t">
        <APIHealthIndicator />
      </div>
    </aside>
  );
}

// Navigation item with tooltip for collapsed state
function NavItem({ href, icon, label, active }) {
  return (
    <Tooltip content={label} side="right" sideOffset={8}>
      <Link
        href={href}
        className={cn(
          'flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
          active
            ? 'bg-primary-50 text-primary-600'
            : 'text-neutral-600 hover:bg-neutral-100'
        )}
      >
        {icon}
        <span className="hidden lg:block">{label}</span>
      </Link>
    </Tooltip>
  );
}
```

#### Mobile Navigation

```tsx
// Bottom navigation for mobile
function MobileNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t md:hidden z-50">
      <div className="flex justify-around py-2">
        {mobileNavItems.map(item => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'flex flex-col items-center py-1 px-3',
              active ? 'text-primary-600' : 'text-neutral-500'
            )}
          >
            {item.icon}
            <span className="text-xs mt-1">{item.label}</span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
```

---

### Animation Guidelines (Extended)

```typescript
// Framer Motion animation presets
const animations = {
  // Page transitions
  pageEnter: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
    transition: { duration: 0.3, ease: 'easeOut' },
  },

  // Modal animations
  modalOverlay: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
    transition: { duration: 0.2 },
  },
  modalContent: {
    initial: { opacity: 0, scale: 0.95, y: 10 },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.95, y: 10 },
    transition: { duration: 0.2, ease: 'easeOut' },
  },

  // List item stagger
  listContainer: {
    animate: { transition: { staggerChildren: 0.05 } },
  },
  listItem: {
    initial: { opacity: 0, x: -10 },
    animate: { opacity: 1, x: 0 },
  },

  // Success celebration
  successPop: {
    initial: { scale: 0 },
    animate: { scale: [0, 1.2, 1] },
    transition: { duration: 0.4, ease: 'easeOut' },
  },

  // Gauge fill animation
  gaugeFill: {
    initial: { strokeDashoffset: 283 },
    animate: { strokeDashoffset: 0 },
    transition: { duration: 1, ease: 'easeInOut', delay: 0.3 },
  },

  // Reduced motion fallback
  reducedMotion: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    transition: { duration: 0.01 },
  },
};

// Respect user preferences
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
```

---

### Dark Mode Design

```typescript
// Dark mode color mappings
const darkModeColors = {
  // Backgrounds
  'bg-white': 'dark:bg-neutral-800',
  'bg-neutral-50': 'dark:bg-neutral-900',
  'bg-neutral-100': 'dark:bg-neutral-800',

  // Text
  'text-neutral-900': 'dark:text-neutral-50',
  'text-neutral-700': 'dark:text-neutral-200',
  'text-neutral-500': 'dark:text-neutral-400',

  // Borders
  'border-neutral-200': 'dark:border-neutral-700',

  // Primary adjustments (slightly lighter in dark mode)
  'bg-primary-500': 'dark:bg-primary-400',
  'text-primary-600': 'dark:text-primary-400',
};

// Component dark mode example
function Card({ children }) {
  return (
    <div className={cn(
      'rounded-lg border p-4',
      'bg-white border-neutral-200',
      'dark:bg-neutral-800 dark:border-neutral-700'
    )}>
      {children}
    </div>
  );
}
```

---

### Onboarding Flow

```tsx
// First-time user onboarding
function OnboardingFlow() {
  const steps = [
    {
      target: '[data-onboarding="api-status"]',
      title: 'API Connection',
      content: 'This indicator shows if the biometric API is running.',
    },
    {
      target: '[data-onboarding="enroll-button"]',
      title: 'Start Here',
      content: 'Begin by enrolling a face to enable all features.',
    },
    {
      target: '[data-onboarding="webcam"]',
      title: 'Camera Access',
      content: 'Allow camera access for real-time face capture.',
    },
  ];

  return (
    <OnboardingTour
      steps={steps}
      showProgress
      onComplete={markOnboardingComplete}
      onSkip={markOnboardingComplete}
    />
  );
}
```

---

### Contextual Help

```tsx
// Help tooltip component
function HelpTooltip({ content }) {
  return (
    <Tooltip content={content}>
      <button className="text-neutral-400 hover:text-neutral-600 ml-1">
        <HelpCircleIcon className="w-4 h-4" />
      </button>
    </Tooltip>
  );
}

// Usage
<Label>
  Similarity Threshold
  <HelpTooltip content="Minimum similarity score (0-1) required for a positive match. Higher values are more strict." />
</Label>

// Inline help text
<div className="bg-info-50 border border-info-200 rounded-lg p-4">
  <div className="flex gap-3">
    <InfoIcon className="w-5 h-5 text-info-600 flex-shrink-0 mt-0.5" />
    <div>
      <h4 className="font-medium text-info-800">Pro Tip</h4>
      <p className="text-sm text-info-700">
        For best results, ensure the face is well-lit and centered in the frame.
      </p>
    </div>
  </div>
</div>
```

---

## Software Engineering Compliance

This section ensures full compliance with the SE Checklist. Every principle, pattern, and practice is explicitly addressed.

---

### Core Design Principles

#### DRY (Don't Repeat Yourself)

| Violation | Solution |
|-----------|----------|
| Duplicate API calls | Centralized `lib/api/client.ts` with reusable methods |
| Repeated form validation | Shared Zod schemas in `lib/validation/schemas.ts` |
| Similar component styles | Tailwind utility classes + `cn()` helper |
| Duplicate error handling | Centralized `ErrorBoundary` + `useErrorHandler` hook |

```typescript
// lib/validation/schemas.ts - Single source of truth
export const userIdSchema = z.string().min(1).max(100);
export const thresholdSchema = z.number().min(0).max(1);
export const imageSchema = z.instanceof(File).refine(
  (file) => ['image/jpeg', 'image/png'].includes(file.type),
  'Must be JPEG or PNG'
);
```

#### KISS (Keep It Simple, Stupid)

| Principle | Implementation |
|-----------|----------------|
| Simple component APIs | Max 5-7 props per component, sensible defaults |
| Flat state structure | Avoid nested state objects, use normalized data |
| Direct data flow | Props down, events up - avoid prop drilling with context only when necessary |
| No premature abstraction | Create abstractions only after 3+ repetitions |

#### YAGNI (You Aren't Gonna Need It)

| Avoid | Instead |
|-------|---------|
| Generic "future-proof" utilities | Build specific solutions for current needs |
| Unused component variants | Add variants only when needed |
| Over-configurable components | Start simple, add options when required |
| Premature optimization | Profile first, optimize bottlenecks only |

#### Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION (pages/)      │  What to render                   │
├─────────────────────────────────────────────────────────────────┤
│  COMPONENTS (components/)   │  How to render                    │
├─────────────────────────────────────────────────────────────────┤
│  BUSINESS LOGIC (hooks/)    │  What to do                       │
├─────────────────────────────────────────────────────────────────┤
│  DATA ACCESS (lib/api/)     │  Where to get/send data           │
├─────────────────────────────────────────────────────────────────┤
│  STATE (lib/store/)         │  What to remember                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Composition Over Inheritance

```typescript
// ❌ BAD: Inheritance
class EnrollmentForm extends BaseForm { ... }

// ✅ GOOD: Composition
function EnrollmentForm() {
  return (
    <FormContainer>
      <FormHeader title="Enroll Face" />
      <ImageUploader onUpload={handleUpload} />
      <FormActions onSubmit={handleSubmit} />
    </FormContainer>
  );
}
```

---

### SOLID Principles (Detailed)

#### S - Single Responsibility Principle

Each module has ONE reason to change:

| Module | Single Responsibility | Changes Only When |
|--------|----------------------|-------------------|
| `WebcamCapture` | Camera access & capture | Camera API changes |
| `ImageUploader` | File upload & validation | Upload requirements change |
| `SimilarityGauge` | Score visualization | Display requirements change |
| `useEnrollFace` | Enrollment API calls | Enrollment API changes |
| `apiClient` | HTTP communication | API protocol changes |

```typescript
// ✅ GOOD: Single responsibility
// webcam-capture.tsx - ONLY handles camera
export function WebcamCapture({ onCapture }: Props) {
  // Only camera logic here
}

// image-processor.ts - ONLY handles image processing
export function processImage(image: File): ProcessedImage {
  // Only processing logic here
}
```

#### O - Open/Closed Principle

Components open for extension, closed for modification:

```typescript
// ✅ GOOD: Extend via props, not modification
interface ResultCardProps {
  title: string;
  value: string | number;
  icon?: React.ReactNode;           // Extension point
  variant?: 'default' | 'success' | 'error';  // Extension point
  footer?: React.ReactNode;         // Extension point
  className?: string;               // Extension point
}

// Usage - extended without modifying ResultCard
<ResultCard
  title="Match Score"
  value="94.5%"
  icon={<CheckIcon />}
  variant="success"
  footer={<MatchDetails />}
/>
```

#### L - Liskov Substitution Principle

All input components implement common interface:

```typescript
// lib/types/form.ts - Common interface
interface FormInputProps<T> {
  value: T;
  onChange: (value: T) => void;
  error?: string;
  disabled?: boolean;
  required?: boolean;
}

// All inputs are substitutable
const TextInput: FC<FormInputProps<string>> = ...
const NumberInput: FC<FormInputProps<number>> = ...
const FileInput: FC<FormInputProps<File | null>> = ...

// Can be used interchangeably in FormField
<FormField input={TextInput} />
<FormField input={NumberInput} />
<FormField input={FileInput} />
```

#### I - Interface Segregation Principle

Clients depend only on what they need:

```typescript
// ❌ BAD: One fat interface
interface BiometricAPI {
  enrollFace(): Promise<void>;
  verifyFace(): Promise<void>;
  searchFace(): Promise<void>;
  checkLiveness(): Promise<void>;
  getMetrics(): Promise<void>;
  configureWebhooks(): Promise<void>;
  // ... 20 more methods
}

// ✅ GOOD: Segregated interfaces
interface FaceEnrollmentAPI {
  enrollFace(params: EnrollParams): Promise<EnrollResult>;
  checkDuplicate(image: File): Promise<boolean>;
}

interface FaceVerificationAPI {
  verifyFace(params: VerifyParams): Promise<VerifyResult>;
}

interface LivenessAPI {
  checkPassiveLiveness(image: File): Promise<LivenessResult>;
  checkActiveLiveness(frames: File[]): Promise<LivenessResult>;
}
```

#### D - Dependency Inversion Principle

Depend on abstractions, not concretions:

```typescript
// lib/api/interfaces.ts - Abstractions
interface IAPIClient {
  get<T>(url: string): Promise<T>;
  post<T>(url: string, data: unknown): Promise<T>;
}

interface IFaceService {
  enroll(params: EnrollParams): Promise<EnrollResult>;
  verify(params: VerifyParams): Promise<VerifyResult>;
}

// lib/api/client.ts - Concrete implementation
class HTTPAPIClient implements IAPIClient { ... }
class FaceService implements IFaceService {
  constructor(private client: IAPIClient) {} // Injected dependency
}

// lib/api/mock-client.ts - Mock for testing
class MockAPIClient implements IAPIClient { ... }

// Context provider injects the dependency
const APIContext = createContext<IAPIClient>(new HTTPAPIClient());
```

---

### Design Patterns (Complete)

#### Creational Patterns

| Pattern | Implementation | Location |
|---------|----------------|----------|
| **Factory** | Component factories for dynamic rendering | `lib/factories/` |
| **Builder** | Complex form/request construction | `lib/builders/` |
| **Singleton** | API client, WebSocket manager instances | `lib/api/client.ts` |

```typescript
// Factory Pattern - Component Factory
// lib/factories/result-factory.tsx
export function createResultComponent(type: ResultType): React.FC<ResultProps> {
  switch (type) {
    case 'enrollment': return EnrollmentResult;
    case 'verification': return VerificationResult;
    case 'search': return SearchResult;
    default: return GenericResult;
  }
}

// Builder Pattern - Request Builder
// lib/builders/enrollment-builder.ts
export class EnrollmentRequestBuilder {
  private request: Partial<EnrollmentRequest> = {};

  withUserId(userId: string): this {
    this.request.userId = userId;
    return this;
  }

  withImage(image: File): this {
    this.request.image = image;
    return this;
  }

  withMetadata(metadata: Record<string, string>): this {
    this.request.metadata = metadata;
    return this;
  }

  build(): EnrollmentRequest {
    if (!this.request.userId || !this.request.image) {
      throw new Error('userId and image are required');
    }
    return this.request as EnrollmentRequest;
  }
}

// Usage
const request = new EnrollmentRequestBuilder()
  .withUserId('user-123')
  .withImage(imageFile)
  .withMetadata({ source: 'webcam' })
  .build();
```

#### Structural Patterns

| Pattern | Implementation | Location |
|---------|----------------|----------|
| **Adapter** | API response normalization | `lib/adapters/` |
| **Facade** | Simplified biometric operations | `lib/facades/` |
| **Decorator** | HOCs for auth, loading states | `lib/decorators/` |
| **Composite** | Nested form/layout structures | Components |

```typescript
// Adapter Pattern - Normalize API responses
// lib/adapters/face-adapter.ts
export function adaptEnrollmentResponse(raw: RawAPIResponse): EnrollmentResult {
  return {
    userId: raw.user_id,
    faceId: raw.face_id,
    quality: raw.quality_score,
    enrolledAt: new Date(raw.created_at),
  };
}

// Facade Pattern - Simplified interface
// lib/facades/biometric-facade.ts
export class BiometricFacade {
  constructor(
    private faceService: IFaceService,
    private livenessService: ILivenessService,
    private qualityService: IQualityService
  ) {}

  async enrollWithValidation(image: File, userId: string): Promise<EnrollmentResult> {
    // Step 1: Check quality
    const quality = await this.qualityService.analyze(image);
    if (quality.score < 0.7) throw new QualityError(quality);

    // Step 2: Check liveness
    const liveness = await this.livenessService.check(image);
    if (!liveness.isLive) throw new LivenessError(liveness);

    // Step 3: Enroll
    return this.faceService.enroll({ image, userId });
  }
}

// Decorator Pattern - HOC for loading state
// lib/decorators/with-loading.tsx
export function withLoading<P extends object>(
  Component: React.FC<P>
): React.FC<P & { isLoading?: boolean }> {
  return function WithLoading({ isLoading, ...props }) {
    if (isLoading) return <LoadingSpinner />;
    return <Component {...(props as P)} />;
  };
}
```

#### Behavioral Patterns

| Pattern | Implementation | Location |
|---------|----------------|----------|
| **Observer** | Event subscriptions, WebSocket | `lib/websocket/` |
| **Strategy** | Interchangeable algorithms | `lib/strategies/` |
| **Command** | Undo/redo, action queue | `lib/commands/` |
| **State** | UI state machines | `lib/state-machines/` |

```typescript
// Strategy Pattern - Interchangeable liveness algorithms
// lib/strategies/liveness-strategy.ts
interface LivenessStrategy {
  check(image: File): Promise<LivenessResult>;
}

class PassiveLivenessStrategy implements LivenessStrategy {
  async check(image: File): Promise<LivenessResult> {
    return apiClient.post('/liveness/passive', { image });
  }
}

class ActiveLivenessStrategy implements LivenessStrategy {
  async check(frames: File[]): Promise<LivenessResult> {
    return apiClient.post('/liveness/active', { frames });
  }
}

// Context uses strategy
class LivenessChecker {
  constructor(private strategy: LivenessStrategy) {}

  setStrategy(strategy: LivenessStrategy): void {
    this.strategy = strategy;
  }

  async check(input: File | File[]): Promise<LivenessResult> {
    return this.strategy.check(input);
  }
}

// State Pattern - UI State Machine
// lib/state-machines/enrollment-machine.ts
type EnrollmentState = 'idle' | 'capturing' | 'processing' | 'success' | 'error';

interface EnrollmentMachine {
  state: EnrollmentState;
  transition(action: EnrollmentAction): void;
}

const enrollmentMachine: EnrollmentMachine = {
  state: 'idle',
  transition(action) {
    switch (this.state) {
      case 'idle':
        if (action === 'START_CAPTURE') this.state = 'capturing';
        break;
      case 'capturing':
        if (action === 'CAPTURE_COMPLETE') this.state = 'processing';
        if (action === 'CANCEL') this.state = 'idle';
        break;
      case 'processing':
        if (action === 'SUCCESS') this.state = 'success';
        if (action === 'ERROR') this.state = 'error';
        break;
      // ...
    }
  }
};
```

---

### Anti-Patterns Avoidance

#### Code Smells to Prevent

| Anti-Pattern | Prevention Strategy | Enforcement |
|--------------|---------------------|-------------|
| **God Object** | Max 200 lines per component, single responsibility | ESLint rule |
| **Spaghetti Code** | Clear layer boundaries, no cross-layer imports | Import restrictions |
| **Magic Numbers** | Named constants in `lib/constants/` | ESLint no-magic-numbers |
| **Dead Code** | CI removes unused exports | ts-prune in CI |
| **Feature Envy** | Colocate logic with data it operates on | Code review |
| **Long Methods** | Max 30 lines per function | ESLint max-lines-per-function |
| **Large Classes** | Max 300 lines per file | ESLint max-lines |

```typescript
// lib/constants/thresholds.ts - No magic numbers
export const SIMILARITY_THRESHOLDS = {
  HIGH_CONFIDENCE: 0.85,
  MEDIUM_CONFIDENCE: 0.70,
  LOW_CONFIDENCE: 0.55,
  MINIMUM: 0.40,
} as const;

export const FILE_SIZE_LIMITS = {
  MAX_IMAGE_SIZE_MB: 10,
  MAX_IMAGE_SIZE_BYTES: 10 * 1024 * 1024,
} as const;

export const TIMING = {
  DEBOUNCE_MS: 300,
  API_TIMEOUT_MS: 30000,
  TOAST_DURATION_MS: 5000,
} as const;
```

#### Architecture Anti-Patterns

| Anti-Pattern | Prevention |
|--------------|------------|
| **Big Ball of Mud** | Strict folder structure, layer boundaries |
| **Golden Hammer** | Choose right tool for each problem |
| **Lava Flow** | Regular dead code removal, no commented code |
| **Vendor Lock-in** | Abstract external dependencies behind interfaces |
| **Premature Optimization** | Profile before optimizing |

---

### Clean Code Guidelines

#### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| **Components** | PascalCase | `WebcamCapture`, `SimilarityGauge` |
| **Hooks** | camelCase with `use` prefix | `useWebcam`, `useEnrollFace` |
| **Utilities** | camelCase | `formatSimilarity`, `validateImage` |
| **Constants** | SCREAMING_SNAKE_CASE | `MAX_FILE_SIZE`, `API_TIMEOUT` |
| **Types/Interfaces** | PascalCase | `EnrollmentResult`, `VerifyParams` |
| **Files** | kebab-case | `webcam-capture.tsx`, `use-webcam.ts` |
| **Folders** | kebab-case | `components/`, `lib/api/` |

#### Function Guidelines

```typescript
// ✅ GOOD: Small, focused functions
function validateImageSize(file: File): ValidationResult {
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, error: 'File too large' };
  }
  return { valid: true };
}

function validateImageType(file: File): ValidationResult {
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return { valid: false, error: 'Invalid file type' };
  }
  return { valid: true };
}

function validateImage(file: File): ValidationResult {
  const sizeResult = validateImageSize(file);
  if (!sizeResult.valid) return sizeResult;

  const typeResult = validateImageType(file);
  if (!typeResult.valid) return typeResult;

  return { valid: true };
}
```

#### Comment Guidelines

```typescript
// ✅ GOOD: Comments explain WHY, not WHAT
// Using 0.6 threshold because facial recognition accuracy drops
// significantly below this value based on our benchmarks
const MINIMUM_SIMILARITY_THRESHOLD = 0.6;

// ❌ BAD: Comment explains WHAT (obvious from code)
// Set the threshold to 0.6
const threshold = 0.6;
```

---

### Error Handling Strategy

#### Error Hierarchy

```typescript
// lib/errors/index.ts
export class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly isOperational: boolean = true
  ) {
    super(message);
    this.name = this.constructor.name;
  }
}

export class APIError extends AppError {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly endpoint: string
  ) {
    super(message, `API_${statusCode}`, true);
  }
}

export class ValidationError extends AppError {
  constructor(
    message: string,
    public readonly field: string
  ) {
    super(message, 'VALIDATION_ERROR', true);
  }
}

export class BiometricError extends AppError {
  constructor(
    message: string,
    public readonly type: 'quality' | 'liveness' | 'duplicate'
  ) {
    super(message, `BIOMETRIC_${type.toUpperCase()}`, true);
  }
}
```

#### Error Handling Patterns

```typescript
// hooks/use-error-handler.ts
export function useErrorHandler() {
  const { toast } = useToast();

  const handleError = useCallback((error: unknown) => {
    if (error instanceof ValidationError) {
      toast.error(`Validation failed: ${error.message}`);
    } else if (error instanceof APIError) {
      toast.error(`API error: ${error.message}`);
      // Log to monitoring service
      logError(error);
    } else if (error instanceof BiometricError) {
      toast.warning(`Biometric check failed: ${error.message}`);
    } else {
      toast.error('An unexpected error occurred');
      logError(error);
    }
  }, [toast]);

  return { handleError };
}

// Usage in components
function EnrollmentForm() {
  const { handleError } = useErrorHandler();
  const enrollMutation = useEnrollFace();

  const handleSubmit = async (data: FormData) => {
    try {
      await enrollMutation.mutateAsync(data);
      toast.success('Enrollment successful');
    } catch (error) {
      handleError(error);
    }
  };
}
```

#### Null Safety

```typescript
// ✅ GOOD: Use optional chaining and nullish coalescing
const userName = user?.name ?? 'Unknown';
const threshold = settings?.threshold ?? DEFAULT_THRESHOLD;

// ✅ GOOD: Type-safe null checks
function processResult(result: Result | null): void {
  if (!result) {
    throw new AppError('Result is required', 'NULL_RESULT');
  }
  // TypeScript now knows result is not null
  console.log(result.value);
}
```

---

### Security Guidelines

#### Input Validation

```typescript
// lib/validation/sanitize.ts
import DOMPurify from 'dompurify';

export function sanitizeInput(input: string): string {
  return DOMPurify.sanitize(input.trim());
}

export function validateUserId(userId: string): void {
  const sanitized = sanitizeInput(userId);
  if (sanitized.length < 1 || sanitized.length > 100) {
    throw new ValidationError('User ID must be 1-100 characters', 'userId');
  }
  if (!/^[a-zA-Z0-9_-]+$/.test(sanitized)) {
    throw new ValidationError('User ID contains invalid characters', 'userId');
  }
}
```

#### XSS Prevention

```typescript
// ✅ React automatically escapes JSX - safe by default
return <div>{userInput}</div>;

// ⚠️ DANGEROUS: Only use when absolutely necessary
return <div dangerouslySetInnerHTML={{ __html: sanitizedHTML }} />;

// ✅ GOOD: Use DOMPurify for any HTML content
const safeHTML = DOMPurify.sanitize(untrustedHTML);
```

#### CSRF Protection

```typescript
// lib/api/client.ts
class SecureAPIClient {
  private csrfToken: string | null = null;

  async request<T>(config: RequestConfig): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Include CSRF token for mutating requests
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method)) {
      if (this.csrfToken) {
        headers['X-CSRF-Token'] = this.csrfToken;
      }
    }

    return fetch(config.url, { ...config, headers });
  }
}
```

#### Secure Data Handling

| Data Type | Handling |
|-----------|----------|
| **API Keys** | Never in client code, use server-side only |
| **User Images** | Temporary URLs, auto-expire, no localStorage |
| **Session Data** | httpOnly cookies, not localStorage |
| **Sensitive Logs** | Never log PII, mask sensitive data |

---

### Performance Best Practices

#### Lazy Loading

```typescript
// ✅ GOOD: Lazy load heavy components
const FacialLandmarksViewer = lazy(() => import('@/components/biometric/landmark-viewer'));
const BatchProcessor = lazy(() => import('@/components/batch-processor'));

// Usage with Suspense
<Suspense fallback={<LoadingSpinner />}>
  <FacialLandmarksViewer />
</Suspense>
```

#### Memoization

```typescript
// ✅ GOOD: Memoize expensive computations
const processedResults = useMemo(() => {
  return results.map(processResult).filter(filterResult);
}, [results]);

// ✅ GOOD: Memoize callbacks passed to children
const handleCapture = useCallback((image: string) => {
  setImage(image);
}, []);
```

#### Image Optimization

```typescript
// ✅ GOOD: Resize images before upload
async function optimizeImage(file: File): Promise<File> {
  const maxDimension = 1920;
  const quality = 0.85;

  const img = await createImageBitmap(file);
  const scale = Math.min(1, maxDimension / Math.max(img.width, img.height));

  const canvas = new OffscreenCanvas(
    img.width * scale,
    img.height * scale
  );
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

  const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality });
  return new File([blob], file.name, { type: 'image/jpeg' });
}
```

---

### Testing Strategy (Detailed)

#### AAA Pattern

```typescript
// tests/unit/use-enroll-face.test.ts
describe('useEnrollFace', () => {
  it('should enroll face successfully', async () => {
    // Arrange
    const mockImage = new File([''], 'test.jpg', { type: 'image/jpeg' });
    const mockUserId = 'user-123';
    const mockResponse = { faceId: 'face-456', quality: 0.95 };
    server.use(
      rest.post('/api/faces/enroll', (req, res, ctx) =>
        res(ctx.json(mockResponse))
      )
    );

    // Act
    const { result } = renderHook(() => useEnrollFace());
    await act(async () => {
      await result.current.mutateAsync({ image: mockImage, userId: mockUserId });
    });

    // Assert
    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.isSuccess).toBe(true);
  });
});
```

#### Coverage Targets

| Area | Minimum Coverage |
|------|-----------------|
| **Hooks** | 90% |
| **Utilities** | 95% |
| **Components** | 80% |
| **Integration** | 70% |
| **E2E Critical Paths** | 100% |

#### Edge Case Testing

```typescript
describe('ImageUploader', () => {
  // Happy path
  it('should accept valid JPEG image');
  it('should accept valid PNG image');

  // Edge cases
  it('should reject file over size limit');
  it('should reject invalid file type');
  it('should handle empty file');
  it('should handle corrupted image');
  it('should handle network failure during upload');
  it('should handle concurrent uploads');
  it('should handle upload cancellation');
});
```

---

### Version Control Guidelines

#### Commit Message Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code refactoring |
| `docs` | Documentation |
| `test` | Test additions/changes |
| `style` | Formatting, no code change |
| `chore` | Build, config changes |

Example:
```
feat(enrollment): add duplicate face detection

- Implement check for existing face embeddings
- Show warning dialog when duplicate detected
- Add option to proceed or cancel enrollment

Closes #123
```

#### Branching Strategy

```
main (protected)
  └── develop
        ├── feature/enrollment-page
        ├── feature/verification-page
        ├── fix/camera-permission-error
        └── refactor/api-client
```

---

### Documentation Standards

#### Component Documentation

```typescript
/**
 * Captures images from user's webcam with face detection overlay.
 *
 * @component
 * @example
 * ```tsx
 * <WebcamCapture
 *   onCapture={(image) => console.log('Captured:', image)}
 *   aspectRatio="1:1"
 *   showOverlay
 * />
 * ```
 *
 * @remarks
 * Requires camera permissions. Will show error state if permission denied.
 */
export function WebcamCapture({
  onCapture,
  onError,
  aspectRatio = '4:3',
  showOverlay = false,
}: WebcamCaptureProps): JSX.Element {
  // ...
}
```

#### API Documentation

```typescript
/**
 * Enrolls a face for future verification/search operations.
 *
 * @param params - Enrollment parameters
 * @param params.image - Face image file (JPEG/PNG, max 10MB)
 * @param params.userId - Unique identifier for the user
 * @param params.metadata - Optional metadata to store with enrollment
 *
 * @returns Promise resolving to enrollment result with face ID and quality score
 *
 * @throws {ValidationError} If image or userId is invalid
 * @throws {BiometricError} If face quality is too low or duplicate detected
 * @throws {APIError} If server returns error response
 *
 * @example
 * ```ts
 * const result = await enrollFace({
 *   image: capturedImage,
 *   userId: 'user-123',
 *   metadata: { source: 'webcam' }
 * });
 * console.log(`Enrolled with face ID: ${result.faceId}`);
 * ```
 */
export async function enrollFace(params: EnrollParams): Promise<EnrollResult> {
  // ...
}
```

---

## API Design Standards

### RESTful Conventions

#### URL Structure

```
GET    /api/v1/faces                    # List all faces
POST   /api/v1/faces                    # Create/enroll face
GET    /api/v1/faces/{faceId}           # Get specific face
DELETE /api/v1/faces/{faceId}           # Delete face
POST   /api/v1/faces/verify             # Verify face (action)
POST   /api/v1/faces/search             # Search faces (action)

GET    /api/v1/liveness/challenges      # Get available challenges
POST   /api/v1/liveness/check           # Perform liveness check

GET    /api/v1/proctoring/sessions      # List sessions
POST   /api/v1/proctoring/sessions      # Create session
GET    /api/v1/proctoring/sessions/{id} # Get session details
WS     /api/v1/proctoring/sessions/{id}/stream  # WebSocket stream
```

#### HTTP Methods

| Method | Purpose | Idempotent | Safe |
|--------|---------|------------|------|
| `GET` | Retrieve resource(s) | Yes | Yes |
| `POST` | Create resource or action | No | No |
| `PUT` | Replace resource entirely | Yes | No |
| `PATCH` | Partial update | No | No |
| `DELETE` | Remove resource | Yes | No |

#### API Versioning

```typescript
// URL versioning (recommended)
const API_V1 = '/api/v1';
const API_V2 = '/api/v2';

// Version in Accept header (alternative)
// Accept: application/vnd.biometric.v1+json
```

### Request/Response Standards

#### Request Format

```typescript
// POST /api/v1/faces
interface EnrollFaceRequest {
  userId: string;                    // Required
  image: string;                     // Base64 or multipart
  metadata?: Record<string, string>; // Optional
  options?: {
    qualityThreshold?: number;       // Default: 0.7
    checkDuplicate?: boolean;        // Default: true
  };
}

// Query parameters for filtering/pagination
// GET /api/v1/faces?page=1&limit=20&sort=-createdAt&filter[quality_gte]=0.8
```

#### Response Format

```typescript
// Success response
interface APIResponse<T> {
  success: true;
  data: T;
  meta?: {
    page?: number;
    limit?: number;
    total?: number;
    totalPages?: number;
  };
}

// Error response
interface APIErrorResponse {
  success: false;
  error: {
    code: string;           // Machine-readable: "FACE_NOT_DETECTED"
    message: string;        // Human-readable: "No face detected in image"
    details?: unknown;      // Additional context
    field?: string;         // For validation errors
    requestId: string;      // For debugging/support
  };
}
```

#### HTTP Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| `200` | OK | Successful GET, PUT, PATCH |
| `201` | Created | Successful POST creating resource |
| `204` | No Content | Successful DELETE |
| `400` | Bad Request | Validation error, malformed request |
| `401` | Unauthorized | Missing/invalid authentication |
| `403` | Forbidden | Authenticated but not authorized |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Duplicate resource (e.g., face already enrolled) |
| `422` | Unprocessable | Business logic error (e.g., low quality) |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Error | Server error |
| `503` | Service Unavailable | Maintenance/overload |

### Pagination

```typescript
// Cursor-based pagination (preferred for large datasets)
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    cursor: string | null;      // Current position
    nextCursor: string | null;  // Next page cursor
    hasMore: boolean;
    limit: number;
  };
}

// Offset-based pagination (for smaller datasets)
interface OffsetPaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}
```

### Error Handling

```typescript
// lib/api/errors.ts
const API_ERROR_CODES = {
  // Validation errors (400)
  INVALID_REQUEST: 'INVALID_REQUEST',
  INVALID_IMAGE_FORMAT: 'INVALID_IMAGE_FORMAT',
  IMAGE_TOO_LARGE: 'IMAGE_TOO_LARGE',
  MISSING_REQUIRED_FIELD: 'MISSING_REQUIRED_FIELD',

  // Authentication errors (401)
  INVALID_TOKEN: 'INVALID_TOKEN',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',

  // Business logic errors (422)
  FACE_NOT_DETECTED: 'FACE_NOT_DETECTED',
  MULTIPLE_FACES_DETECTED: 'MULTIPLE_FACES_DETECTED',
  LOW_QUALITY_IMAGE: 'LOW_QUALITY_IMAGE',
  LIVENESS_CHECK_FAILED: 'LIVENESS_CHECK_FAILED',
  DUPLICATE_FACE: 'DUPLICATE_FACE',
  USER_NOT_FOUND: 'USER_NOT_FOUND',

  // Rate limiting (429)
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',

  // Server errors (500)
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  MODEL_INFERENCE_FAILED: 'MODEL_INFERENCE_FAILED',
} as const;
```

---

## Internationalization (i18n)

### Setup

```typescript
// lib/i18n/config.ts
import { createInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';

export const SUPPORTED_LOCALES = ['en', 'tr'] as const;
export type Locale = typeof SUPPORTED_LOCALES[number];

export const DEFAULT_LOCALE: Locale = 'en';

const i18n = createInstance();

i18n
  .use(initReactI18next)
  .init({
    lng: DEFAULT_LOCALE,
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: SUPPORTED_LOCALES,
    defaultNS: 'common',
    interpolation: {
      escapeValue: false, // React already escapes
    },
  });

export default i18n;
```

### Translation Structure

```
src/
├── locales/
│   ├── en/
│   │   ├── common.json       # Shared translations
│   │   ├── enrollment.json   # Enrollment page
│   │   ├── verification.json # Verification page
│   │   ├── errors.json       # Error messages
│   │   └── validation.json   # Form validation
│   └── tr/
│       ├── common.json
│       ├── enrollment.json
│       ├── verification.json
│       ├── errors.json
│       └── validation.json
```

### Translation Files

```json
// locales/en/common.json
{
  "app": {
    "name": "Biometric Demo",
    "tagline": "Professional Face Recognition System"
  },
  "nav": {
    "dashboard": "Dashboard",
    "enrollment": "Face Enrollment",
    "verification": "Verification",
    "search": "Face Search",
    "liveness": "Liveness Detection"
  },
  "actions": {
    "submit": "Submit",
    "cancel": "Cancel",
    "retry": "Try Again",
    "capture": "Capture",
    "upload": "Upload Image"
  },
  "status": {
    "loading": "Loading...",
    "processing": "Processing...",
    "success": "Success",
    "error": "Error"
  }
}

// locales/tr/common.json
{
  "app": {
    "name": "Biyometrik Demo",
    "tagline": "Profesyonel Yüz Tanıma Sistemi"
  },
  "nav": {
    "dashboard": "Ana Sayfa",
    "enrollment": "Yüz Kaydı",
    "verification": "Doğrulama",
    "search": "Yüz Arama",
    "liveness": "Canlılık Tespiti"
  },
  "actions": {
    "submit": "Gönder",
    "cancel": "İptal",
    "retry": "Tekrar Dene",
    "capture": "Yakala",
    "upload": "Resim Yükle"
  },
  "status": {
    "loading": "Yükleniyor...",
    "processing": "İşleniyor...",
    "success": "Başarılı",
    "error": "Hata"
  }
}
```

### Usage in Components

```tsx
// Using translations
import { useTranslation } from 'react-i18next';

function EnrollmentPage() {
  const { t } = useTranslation(['enrollment', 'common']);

  return (
    <div>
      <h1>{t('enrollment:title')}</h1>
      <Button>{t('common:actions.capture')}</Button>
    </div>
  );
}

// With interpolation
t('enrollment:quality_score', { score: 95 })
// "Quality Score: 95%"

// With pluralization
t('search:results', { count: 5 })
// "5 matches found"
```

### Date/Time/Number Formatting

```typescript
// lib/i18n/formatters.ts
import { format, formatDistance } from 'date-fns';
import { enUS, tr } from 'date-fns/locale';

const locales = { en: enUS, tr };

export function formatDate(date: Date, locale: Locale): string {
  return format(date, 'PPP', { locale: locales[locale] });
}

export function formatRelativeTime(date: Date, locale: Locale): string {
  return formatDistance(date, new Date(), {
    addSuffix: true,
    locale: locales[locale],
  });
}

export function formatNumber(num: number, locale: Locale): string {
  return new Intl.NumberFormat(locale).format(num);
}

export function formatPercent(num: number, locale: Locale): string {
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    minimumFractionDigits: 1,
  }).format(num);
}
```

### RTL Support (Future)

```typescript
// For future Arabic/Hebrew support
const RTL_LOCALES = ['ar', 'he'] as const;

export function isRTL(locale: Locale): boolean {
  return RTL_LOCALES.includes(locale as any);
}

// In layout
<html lang={locale} dir={isRTL(locale) ? 'rtl' : 'ltr'}>
```

---

## Monitoring & Observability

### Logging Strategy

```typescript
// lib/logging/logger.ts
import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  browser: {
    asObject: true,
  },
  base: {
    env: process.env.NODE_ENV,
    version: process.env.NEXT_PUBLIC_APP_VERSION,
  },
});

// Structured logging
export function logInfo(message: string, context?: object): void {
  logger.info({ ...context }, message);
}

export function logError(error: Error, context?: object): void {
  logger.error({
    error: {
      name: error.name,
      message: error.message,
      stack: error.stack,
    },
    ...context,
  }, error.message);
}

export function logAPICall(endpoint: string, duration: number, status: number): void {
  logger.info({
    type: 'api_call',
    endpoint,
    duration,
    status,
  }, `API ${endpoint} responded in ${duration}ms`);
}
```

### Error Tracking (Sentry)

```typescript
// lib/monitoring/sentry.ts
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.1, // 10% of transactions
  beforeSend(event) {
    // Scrub PII
    if (event.user) {
      delete event.user.ip_address;
      delete event.user.email;
    }
    return event;
  },
});

// Capture errors with context
export function captureError(error: Error, context?: Record<string, any>): void {
  Sentry.withScope((scope) => {
    if (context) {
      Object.entries(context).forEach(([key, value]) => {
        scope.setExtra(key, value);
      });
    }
    Sentry.captureException(error);
  });
}

// Track user actions
export function trackAction(action: string, data?: object): void {
  Sentry.addBreadcrumb({
    category: 'user-action',
    message: action,
    data,
    level: 'info',
  });
}
```

### Performance Monitoring

```typescript
// lib/monitoring/performance.ts
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

export function initWebVitals(): void {
  getCLS(sendToAnalytics);
  getFID(sendToAnalytics);
  getFCP(sendToAnalytics);
  getLCP(sendToAnalytics);
  getTTFB(sendToAnalytics);
}

function sendToAnalytics(metric: { name: string; value: number; id: string }): void {
  // Send to analytics service
  const body = JSON.stringify({
    name: metric.name,
    value: metric.value,
    id: metric.id,
    page: window.location.pathname,
  });

  // Use sendBeacon for reliability
  if (navigator.sendBeacon) {
    navigator.sendBeacon('/api/vitals', body);
  }
}
```

### Health Checks

```typescript
// app/api/health/route.ts
export async function GET() {
  const checks = {
    api: await checkAPIHealth(),
    timestamp: new Date().toISOString(),
    version: process.env.NEXT_PUBLIC_APP_VERSION,
    uptime: process.uptime(),
  };

  const isHealthy = checks.api.healthy;

  return Response.json(checks, {
    status: isHealthy ? 200 : 503,
  });
}

async function checkAPIHealth() {
  try {
    const start = Date.now();
    const response = await fetch(`${API_URL}/health`, { timeout: 5000 });
    const latency = Date.now() - start;

    return {
      healthy: response.ok,
      latency,
      status: response.status,
    };
  } catch (error) {
    return {
      healthy: false,
      error: error.message,
    };
  }
}
```

### Metrics Dashboard

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| **API Latency (p95)** | 95th percentile response time | > 2000ms |
| **Error Rate** | Percentage of failed requests | > 1% |
| **LCP** | Largest Contentful Paint | > 2500ms |
| **FID** | First Input Delay | > 100ms |
| **CLS** | Cumulative Layout Shift | > 0.1 |
| **Active Users** | Concurrent users | N/A |
| **Enrollment Success Rate** | % of successful enrollments | < 95% |

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  NODE_VERSION: '20'
  PNPM_VERSION: '8'

jobs:
  # ============================================
  # Quality Gates
  # ============================================
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
        with:
          version: ${{ env.PNPM_VERSION }}
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm type-check

  test:
    name: Unit & Integration Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
        with:
          version: ${{ env.PNPM_VERSION }}
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm test:coverage
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info
          fail_ci_if_error: true

  e2e:
    name: E2E Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
        with:
          version: ${{ env.PNPM_VERSION }}
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm exec playwright install --with-deps
      - run: pnpm build
      - run: pnpm test:e2e
      - uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/

  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Snyk
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high

  # ============================================
  # Build & Deploy
  # ============================================
  build:
    name: Build
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
        with:
          version: ${{ env.PNPM_VERSION }}
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm build
      - name: Upload Build
        uses: actions/upload-artifact@v3
        with:
          name: build
          path: .next/

  deploy-preview:
    name: Deploy Preview
    needs: [build]
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v3
        with:
          name: build
          path: .next/
      - name: Deploy to Vercel Preview
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}

  deploy-production:
    name: Deploy Production
    needs: [build, e2e, security]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v3
        with:
          name: build
          path: .next/
      - name: Deploy to Vercel Production
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

### Quality Gates

| Gate | Tool | Threshold |
|------|------|-----------|
| **Linting** | ESLint | 0 errors |
| **Type Check** | TypeScript | 0 errors |
| **Unit Tests** | Vitest | 100% pass |
| **Coverage** | Vitest | 80% minimum |
| **E2E Tests** | Playwright | 100% pass |
| **Security** | Snyk | No high/critical |
| **Bundle Size** | size-limit | < 200KB JS |
| **Lighthouse** | Lighthouse CI | Score > 90 |

### Pre-commit Hooks

```json
// package.json
{
  "lint-staged": {
    "*.{ts,tsx}": [
      "eslint --fix",
      "prettier --write"
    ],
    "*.{json,md}": [
      "prettier --write"
    ]
  }
}

// .husky/pre-commit
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"
npx lint-staged

// .husky/commit-msg
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"
npx --no -- commitlint --edit "$1"
```

---

## Advanced Security

### OWASP Top 10 Compliance

| Vulnerability | Prevention | Implementation |
|---------------|------------|----------------|
| **A01: Broken Access Control** | Authorization checks | Middleware + route guards |
| **A02: Cryptographic Failures** | TLS, secure storage | HTTPS only, no localStorage for secrets |
| **A03: Injection** | Input validation | Zod schemas, parameterized queries |
| **A04: Insecure Design** | Threat modeling | Security review in design phase |
| **A05: Security Misconfiguration** | Secure defaults | Security headers, CSP |
| **A06: Vulnerable Components** | Dependency scanning | Snyk, npm audit |
| **A07: Auth Failures** | Strong auth | JWT validation, session management |
| **A08: Data Integrity** | Input validation | Schema validation, checksums |
| **A09: Logging Failures** | Audit logging | Structured logs, no PII |
| **A10: SSRF** | URL validation | Allowlist, sanitization |

### Security Headers

```typescript
// next.config.js
const securityHeaders = [
  {
    key: 'X-DNS-Prefetch-Control',
    value: 'on',
  },
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=63072000; includeSubDomains; preload',
  },
  {
    key: 'X-Frame-Options',
    value: 'SAMEORIGIN',
  },
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff',
  },
  {
    key: 'X-XSS-Protection',
    value: '1; mode=block',
  },
  {
    key: 'Referrer-Policy',
    value: 'strict-origin-when-cross-origin',
  },
  {
    key: 'Permissions-Policy',
    value: 'camera=(self), microphone=(), geolocation=()',
  },
];

module.exports = {
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
    ];
  },
};
```

### Content Security Policy

```typescript
// middleware.ts
const CSP = `
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' blob: data:;
  font-src 'self';
  connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL} ws:;
  media-src 'self' blob:;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
`.replace(/\n/g, ' ').trim();

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  response.headers.set('Content-Security-Policy', CSP);
  return response;
}
```

### Rate Limiting

```typescript
// lib/security/rate-limit.ts
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_URL!,
  token: process.env.UPSTASH_REDIS_TOKEN!,
});

// Different limits for different actions
export const rateLimiters = {
  // General API calls: 100 per minute
  api: new Ratelimit({
    redis,
    limiter: Ratelimit.slidingWindow(100, '1 m'),
    prefix: 'ratelimit:api',
  }),

  // Enrollment: 10 per minute (expensive operation)
  enrollment: new Ratelimit({
    redis,
    limiter: Ratelimit.slidingWindow(10, '1 m'),
    prefix: 'ratelimit:enrollment',
  }),

  // Verification: 30 per minute
  verification: new Ratelimit({
    redis,
    limiter: Ratelimit.slidingWindow(30, '1 m'),
    prefix: 'ratelimit:verification',
  }),

  // Search: 20 per minute
  search: new Ratelimit({
    redis,
    limiter: Ratelimit.slidingWindow(20, '1 m'),
    prefix: 'ratelimit:search',
  }),
};

// Usage in API route
export async function checkRateLimit(
  identifier: string,
  limiter: keyof typeof rateLimiters
): Promise<{ success: boolean; remaining: number }> {
  const { success, remaining } = await rateLimiters[limiter].limit(identifier);
  return { success, remaining };
}
```

### Biometric Data Security

```typescript
// lib/security/biometric-handling.ts

// Never store raw biometric data client-side
const BIOMETRIC_RULES = {
  // Images are processed and immediately discarded
  imageRetention: 'none',

  // Only store embeddings (not reversible to image)
  storageType: 'embeddings-only',

  // Encrypt embeddings at rest
  encryption: 'AES-256-GCM',

  // Auto-delete after session ends
  sessionCleanup: true,

  // No caching of biometric data
  caching: 'disabled',
};

// Secure image handling
export async function processSecureImage(file: File): Promise<void> {
  // Convert to processing format
  const imageData = await fileToBase64(file);

  try {
    // Send to API for processing
    await enrollFace(imageData);
  } finally {
    // Clear from memory immediately
    // Note: JavaScript doesn't guarantee immediate GC
    // but we null references to help
    imageData = null;
  }
}

// Clear sensitive data on unmount
export function useBiometricCleanup() {
  useEffect(() => {
    return () => {
      // Clear any cached images
      sessionStorage.removeItem('capturedImage');
      // Revoke object URLs
      URL.revokeObjectURL(imageUrl);
    };
  }, []);
}
```

---

## Data Privacy (GDPR/KVKK)

### Biometric Data Classification

| Data Type | Classification | Retention | Legal Basis |
|-----------|---------------|-----------|-------------|
| **Face Image** | Special Category (Biometric) | Session only | Explicit Consent |
| **Face Embedding** | Special Category (Biometric) | Until deletion request | Explicit Consent |
| **User ID** | Personal Data | With embedding | Legitimate Interest |
| **Metadata** | Personal/Non-personal | With embedding | Legitimate Interest |
| **Logs** | Personal Data | 30 days | Legitimate Interest |

### Consent Management

```typescript
// lib/privacy/consent.ts
interface ConsentRecord {
  userId: string;
  biometricProcessing: boolean;
  dataRetention: boolean;
  timestamp: Date;
  ipAddress?: string;  // Anonymized
  version: string;     // Consent policy version
}

export async function recordConsent(consent: ConsentRecord): Promise<void> {
  // Store consent with timestamp
  await api.post('/consent', {
    ...consent,
    ipAddress: anonymizeIP(consent.ipAddress),
  });
}

// Consent UI component
function BiometricConsentDialog({ onAccept, onDecline }) {
  return (
    <Dialog>
      <DialogTitle>Biometric Data Processing</DialogTitle>
      <DialogContent>
        <p>This demo processes your facial data for:</p>
        <ul>
          <li>Face enrollment and recognition</li>
          <li>Liveness detection</li>
          <li>Quality analysis</li>
        </ul>
        <p>Your data will be:</p>
        <ul>
          <li>Processed locally when possible</li>
          <li>Encrypted in transit and at rest</li>
          <li>Deleted upon your request</li>
        </ul>
        <Checkbox id="consent" required>
          I consent to biometric data processing
        </Checkbox>
      </DialogContent>
      <DialogActions>
        <Button variant="outline" onClick={onDecline}>Decline</Button>
        <Button onClick={onAccept}>Accept & Continue</Button>
      </DialogActions>
    </Dialog>
  );
}
```

### Data Subject Rights (GDPR Article 15-22)

```typescript
// lib/privacy/data-rights.ts

// Right to Access (Article 15)
export async function exportUserData(userId: string): Promise<DataExport> {
  const data = await api.get(`/users/${userId}/export`);
  return {
    enrollments: data.enrollments,
    metadata: data.metadata,
    consentRecords: data.consents,
    activityLog: data.activities,
    exportedAt: new Date().toISOString(),
  };
}

// Right to Erasure (Article 17)
export async function deleteUserData(userId: string): Promise<void> {
  await api.delete(`/users/${userId}`, {
    // Confirm deletion
    headers: { 'X-Confirm-Delete': 'true' },
  });
}

// Right to Rectification (Article 16)
export async function updateUserData(
  userId: string,
  updates: Partial<UserData>
): Promise<void> {
  await api.patch(`/users/${userId}`, updates);
}

// Right to Data Portability (Article 20)
export async function exportPortableData(userId: string): Promise<Blob> {
  const response = await api.get(`/users/${userId}/export`, {
    headers: { 'Accept': 'application/json' },
  });
  return new Blob([JSON.stringify(response, null, 2)], {
    type: 'application/json',
  });
}
```

### KVKK Compliance (Turkish Data Protection)

```typescript
// Additional requirements for KVKK
const KVKK_REQUIREMENTS = {
  // Explicit consent required for biometric data
  explicitConsent: true,

  // Data controller registration with VERBIS
  verbisRegistration: 'REQUIRED',

  // Cross-border transfer restrictions
  crossBorderTransfer: {
    allowed: false,  // Unless adequate protection
    adequateCountries: ['EU', 'EEA'],
  },

  // Data retention limits
  retentionPeriod: {
    biometric: '2 years max',
    logs: '30 days',
  },

  // Turkish language requirement
  consentLanguage: 'tr',
};
```

---

## Browser Compatibility

### Supported Browsers

| Browser | Minimum Version | Notes |
|---------|-----------------|-------|
| **Chrome** | 90+ | Full support |
| **Firefox** | 88+ | Full support |
| **Safari** | 14+ | WebRTC requires HTTPS |
| **Edge** | 90+ | Chromium-based |
| **Opera** | 76+ | Chromium-based |
| **Samsung Internet** | 14+ | Mobile |
| **iOS Safari** | 14.5+ | WebRTC limitations |

### Feature Detection

```typescript
// lib/compatibility/feature-detection.ts
export interface BrowserCapabilities {
  webrtc: boolean;
  mediaDevices: boolean;
  webgl: boolean;
  webSocket: boolean;
  serviceWorker: boolean;
  indexedDB: boolean;
}

export function detectCapabilities(): BrowserCapabilities {
  return {
    webrtc: !!window.RTCPeerConnection,
    mediaDevices: !!(navigator.mediaDevices?.getUserMedia),
    webgl: (() => {
      try {
        const canvas = document.createElement('canvas');
        return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
      } catch {
        return false;
      }
    })(),
    webSocket: 'WebSocket' in window,
    serviceWorker: 'serviceWorker' in navigator,
    indexedDB: 'indexedDB' in window,
  };
}

// Show warning for unsupported browsers
export function BrowserCompatibilityCheck({ children }: { children: React.ReactNode }) {
  const [isSupported, setIsSupported] = useState(true);
  const [missingFeatures, setMissingFeatures] = useState<string[]>([]);

  useEffect(() => {
    const caps = detectCapabilities();
    const missing = [];

    if (!caps.mediaDevices) missing.push('Camera access');
    if (!caps.webrtc) missing.push('WebRTC');
    if (!caps.webSocket) missing.push('WebSocket');

    if (missing.length > 0) {
      setIsSupported(false);
      setMissingFeatures(missing);
    }
  }, []);

  if (!isSupported) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Browser Not Supported</AlertTitle>
        <AlertDescription>
          Your browser is missing: {missingFeatures.join(', ')}.
          Please use a modern browser like Chrome, Firefox, or Edge.
        </AlertDescription>
      </Alert>
    );
  }

  return children;
}
```

### Polyfills

```typescript
// lib/polyfills.ts
// Only load polyfills for older browsers

export async function loadPolyfills(): Promise<void> {
  const polyfills: Promise<void>[] = [];

  // ResizeObserver
  if (!('ResizeObserver' in window)) {
    polyfills.push(
      import('resize-observer-polyfill').then(({ default: RO }) => {
        window.ResizeObserver = RO;
      })
    );
  }

  // IntersectionObserver
  if (!('IntersectionObserver' in window)) {
    polyfills.push(import('intersection-observer'));
  }

  // Fetch (very old browsers)
  if (!('fetch' in window)) {
    polyfills.push(import('whatwg-fetch'));
  }

  await Promise.all(polyfills);
}
```

---

## Offline/PWA Support

### Service Worker Strategy

```typescript
// next.config.js with next-pwa
const withPWA = require('next-pwa')({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
  register: true,
  skipWaiting: true,
  runtimeCaching: [
    {
      // Cache static assets
      urlPattern: /^https:\/\/fonts\.(?:googleapis|gstatic)\.com\/.*/i,
      handler: 'CacheFirst',
      options: {
        cacheName: 'google-fonts',
        expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
      },
    },
    {
      // Cache API responses (except biometric)
      urlPattern: /^https:\/\/api\..*\/(?!faces|liveness).*/i,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'api-cache',
        expiration: { maxEntries: 50, maxAgeSeconds: 60 * 5 },
        networkTimeoutSeconds: 10,
      },
    },
    {
      // Never cache biometric data
      urlPattern: /^https:\/\/api\..*\/(faces|liveness).*/i,
      handler: 'NetworkOnly',
    },
  ],
});
```

### Offline UI

```tsx
// hooks/use-online-status.ts
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
}

// Offline banner component
function OfflineBanner() {
  const isOnline = useOnlineStatus();

  if (isOnline) return null;

  return (
    <div className="fixed top-0 left-0 right-0 bg-warning-500 text-white py-2 px-4 text-center z-50">
      <WifiOffIcon className="inline w-4 h-4 mr-2" />
      You're offline. Some features may be unavailable.
    </div>
  );
}
```

### PWA Manifest

```json
// public/manifest.json
{
  "name": "Biometric Demo",
  "short_name": "BiometricDemo",
  "description": "Professional Face Recognition Demo",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2563eb",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

---

## Bundle Optimization

### Performance Budgets

```javascript
// size-limit.config.js
module.exports = [
  {
    name: 'Total Bundle',
    path: '.next/static/chunks/*.js',
    limit: '200 KB',
    gzip: true,
  },
  {
    name: 'First Load JS',
    path: '.next/static/chunks/pages/_app*.js',
    limit: '100 KB',
    gzip: true,
  },
  {
    name: 'Main Bundle',
    path: '.next/static/chunks/main*.js',
    limit: '50 KB',
    gzip: true,
  },
];
```

### Code Splitting Strategy

```typescript
// Dynamic imports for heavy components
const FacialLandmarks = dynamic(
  () => import('@/components/biometric/facial-landmarks'),
  {
    loading: () => <Skeleton className="h-96" />,
    ssr: false, // Client-only component
  }
);

const BatchProcessor = dynamic(
  () => import('@/components/batch-processor'),
  { loading: () => <Skeleton className="h-64" /> }
);

const AdminDashboard = dynamic(
  () => import('@/components/admin/dashboard'),
  { loading: () => <PageSkeleton /> }
);

// Route-based code splitting (automatic with Next.js App Router)
// Each page in app/ is automatically code-split
```

### Tree Shaking

```typescript
// ✅ GOOD: Named imports enable tree shaking
import { Button, Card, Dialog } from '@/components/ui';
import { formatDate, formatNumber } from '@/lib/utils';

// ❌ BAD: Namespace imports prevent tree shaking
import * as UI from '@/components/ui';
import * as Utils from '@/lib/utils';

// ✅ GOOD: Import only needed lodash functions
import debounce from 'lodash/debounce';
import throttle from 'lodash/throttle';

// ❌ BAD: Import entire lodash
import _ from 'lodash';
```

### Image Optimization

```tsx
// Use Next.js Image for automatic optimization
import Image from 'next/image';

// Optimized image with responsive sizes
<Image
  src="/images/sample-face.jpg"
  alt="Sample face"
  width={400}
  height={400}
  sizes="(max-width: 640px) 100vw, 400px"
  priority={isAboveFold}
  placeholder="blur"
  blurDataURL={blurDataUrl}
/>

// SVG icons - use inline for small icons
import { CheckIcon } from 'lucide-react';
<CheckIcon className="w-4 h-4" />
```

---

## Feature Flags

### Feature Flag System

```typescript
// lib/feature-flags/flags.ts
export const FEATURE_FLAGS = {
  // Enrollment features
  ENROLLMENT_DUPLICATE_CHECK: 'enrollment.duplicate_check',
  ENROLLMENT_QUALITY_THRESHOLD: 'enrollment.quality_threshold',

  // New features (gradual rollout)
  ACTIVE_LIVENESS: 'liveness.active_mode',
  BATCH_PROCESSING: 'batch.enabled',
  REAL_TIME_PROCTORING: 'proctoring.realtime',

  // Experiments
  NEW_SIMILARITY_GAUGE: 'experiment.new_gauge',
  DARK_MODE: 'ui.dark_mode',

  // Operational
  MAINTENANCE_MODE: 'ops.maintenance',
  DEBUG_MODE: 'ops.debug',
} as const;

type FeatureFlag = typeof FEATURE_FLAGS[keyof typeof FEATURE_FLAGS];

// lib/feature-flags/provider.tsx
interface FeatureFlagContext {
  isEnabled: (flag: FeatureFlag) => boolean;
  flags: Record<FeatureFlag, boolean>;
}

export function useFeatureFlag(flag: FeatureFlag): boolean {
  const { flags } = useContext(FeatureFlagContext);
  return flags[flag] ?? false;
}

// Usage
function EnrollmentPage() {
  const showDuplicateCheck = useFeatureFlag(FEATURE_FLAGS.ENROLLMENT_DUPLICATE_CHECK);
  const showActiveLiveness = useFeatureFlag(FEATURE_FLAGS.ACTIVE_LIVENESS);

  return (
    <>
      {showDuplicateCheck && <DuplicateCheckSection />}
      {showActiveLiveness && <ActiveLivenessSection />}
    </>
  );
}
```

### A/B Testing

```typescript
// lib/experiments/ab-testing.ts
interface Experiment {
  id: string;
  name: string;
  variants: string[];
  weights: number[];  // Must sum to 1
}

const EXPERIMENTS: Experiment[] = [
  {
    id: 'gauge-design',
    name: 'Similarity Gauge Design',
    variants: ['control', 'radial', 'linear'],
    weights: [0.34, 0.33, 0.33],
  },
];

export function getExperimentVariant(
  experimentId: string,
  userId: string
): string {
  const experiment = EXPERIMENTS.find(e => e.id === experimentId);
  if (!experiment) return 'control';

  // Deterministic assignment based on userId hash
  const hash = hashString(`${experimentId}:${userId}`);
  const bucket = (hash % 100) / 100;

  let cumulative = 0;
  for (let i = 0; i < experiment.variants.length; i++) {
    cumulative += experiment.weights[i];
    if (bucket < cumulative) {
      return experiment.variants[i];
    }
  }

  return experiment.variants[0];
}
```

---

## Analytics & Telemetry

### Analytics Events

```typescript
// lib/analytics/events.ts
export const ANALYTICS_EVENTS = {
  // Page views
  PAGE_VIEW: 'page_view',

  // User actions
  FACE_CAPTURED: 'face_captured',
  FACE_ENROLLED: 'face_enrolled',
  FACE_VERIFIED: 'face_verified',
  FACE_SEARCHED: 'face_searched',
  LIVENESS_CHECKED: 'liveness_checked',

  // Errors
  ENROLLMENT_FAILED: 'enrollment_failed',
  VERIFICATION_FAILED: 'verification_failed',
  CAMERA_PERMISSION_DENIED: 'camera_permission_denied',

  // Performance
  API_LATENCY: 'api_latency',
  PAGE_LOAD: 'page_load',
} as const;

// lib/analytics/tracker.ts
interface AnalyticsEvent {
  name: string;
  properties?: Record<string, unknown>;
  timestamp: number;
}

class AnalyticsTracker {
  private queue: AnalyticsEvent[] = [];
  private userId: string | null = null;

  identify(userId: string): void {
    this.userId = userId;
  }

  track(name: string, properties?: Record<string, unknown>): void {
    const event: AnalyticsEvent = {
      name,
      properties: {
        ...properties,
        userId: this.userId,
        sessionId: this.getSessionId(),
        page: window.location.pathname,
      },
      timestamp: Date.now(),
    };

    this.queue.push(event);
    this.flush();
  }

  private async flush(): Promise<void> {
    if (this.queue.length === 0) return;

    const events = [...this.queue];
    this.queue = [];

    try {
      await fetch('/api/analytics', {
        method: 'POST',
        body: JSON.stringify({ events }),
        keepalive: true,
      });
    } catch {
      // Re-queue on failure
      this.queue.unshift(...events);
    }
  }
}

export const analytics = new AnalyticsTracker();
```

### Usage Tracking (Privacy-Respecting)

```typescript
// Track without PII
analytics.track(ANALYTICS_EVENTS.FACE_ENROLLED, {
  qualityScore: result.quality,    // OK: not PII
  duration: enrollmentTime,        // OK: performance metric
  source: 'webcam',                // OK: not PII
  // userId: user.id,              // NO: PII
  // faceId: result.faceId,        // NO: could be PII
});

// Anonymized error tracking
analytics.track(ANALYTICS_EVENTS.ENROLLMENT_FAILED, {
  errorCode: error.code,           // OK: machine code
  errorType: error.type,           // OK: category
  // errorMessage: error.message,  // MAYBE: could contain PII
});
```

---

## Developer Experience

### Local Development Setup

```bash
# Quick start script
# scripts/setup.sh

#!/bin/bash
echo "Setting up Biometric Demo UI..."

# Check Node version
NODE_VERSION=$(node -v | cut -d'.' -f1 | sed 's/v//')
if [ "$NODE_VERSION" -lt 18 ]; then
  echo "Error: Node 18+ required"
  exit 1
fi

# Install dependencies
pnpm install

# Copy environment file
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "Created .env.local - please update with your values"
fi

# Generate types from API schema (if available)
pnpm generate:types

# Run initial build to catch errors
pnpm build

echo "Setup complete! Run 'pnpm dev' to start development server"
```

### Development Scripts

```json
// package.json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint . --ext .ts,.tsx",
    "lint:fix": "eslint . --ext .ts,.tsx --fix",
    "type-check": "tsc --noEmit",
    "test": "vitest",
    "test:watch": "vitest --watch",
    "test:coverage": "vitest --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "storybook": "storybook dev -p 6006",
    "storybook:build": "storybook build",
    "generate:types": "openapi-typescript $API_URL/openapi.json -o src/types/api.generated.ts",
    "analyze": "ANALYZE=true next build",
    "prepare": "husky install"
  }
}
```

### Storybook for Components

```typescript
// .storybook/main.ts
import type { StorybookConfig } from '@storybook/nextjs';

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(js|jsx|ts|tsx)'],
  addons: [
    '@storybook/addon-links',
    '@storybook/addon-essentials',
    '@storybook/addon-interactions',
    '@storybook/addon-a11y',
  ],
  framework: {
    name: '@storybook/nextjs',
    options: {},
  },
};

export default config;

// Example story
// src/components/ui/button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './button';

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'primary', 'destructive', 'outline', 'ghost'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: {
    variant: 'primary',
    children: 'Enroll Face',
  },
};

export const Loading: Story = {
  args: {
    variant: 'primary',
    children: 'Processing...',
    isLoading: true,
  },
};
```

### Mock API for Development

```typescript
// lib/api/mock-server.ts
import { http, HttpResponse } from 'msw';
import { setupWorker } from 'msw/browser';

const handlers = [
  // Health check
  http.get('/api/v1/health', () => {
    return HttpResponse.json({ status: 'healthy', version: '1.0.0' });
  }),

  // Enroll face
  http.post('/api/v1/faces', async ({ request }) => {
    await delay(1000); // Simulate processing
    return HttpResponse.json({
      success: true,
      data: {
        faceId: `face_${Date.now()}`,
        quality: 0.92,
        enrolledAt: new Date().toISOString(),
      },
    });
  }),

  // Verify face
  http.post('/api/v1/faces/verify', async () => {
    await delay(800);
    return HttpResponse.json({
      success: true,
      data: {
        match: true,
        similarity: 0.94,
        confidence: 'high',
      },
    });
  }),
];

export const mockServer = setupWorker(...handlers);

// Start in development
if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_USE_MOCKS === 'true') {
  mockServer.start({ onUnhandledRequest: 'bypass' });
}
```

---

## Dependency Management

### Dependency Policy

| Category | Policy |
|----------|--------|
| **Security Updates** | Apply within 24 hours for critical, 1 week for high |
| **Major Updates** | Evaluate quarterly, test thoroughly |
| **Minor Updates** | Apply monthly with testing |
| **Patch Updates** | Apply weekly, auto-merge if tests pass |

### Automated Dependency Updates

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    groups:
      # Group minor/patch updates
      dependencies:
        patterns:
          - "*"
        exclude-patterns:
          - "eslint*"
          - "typescript"
        update-types:
          - "minor"
          - "patch"
    ignore:
      # Don't auto-update major versions
      - dependency-name: "*"
        update-types: ["version-update:semver-major"]
```

### License Compliance

```javascript
// license-checker.config.js
module.exports = {
  // Allowed licenses
  allowed: [
    'MIT',
    'ISC',
    'BSD-2-Clause',
    'BSD-3-Clause',
    'Apache-2.0',
    '0BSD',
    'CC0-1.0',
  ],

  // Explicitly approved packages with other licenses
  exceptions: {
    // Example: package@version: 'reason for approval'
  },

  // Packages to skip (dev-only, not bundled)
  skip: [
    '@types/*',
    'typescript',
    'eslint*',
  ],
};
```

---

## Disaster Recovery

### Backup Strategy

| Data | Backup Frequency | Retention | Location |
|------|------------------|-----------|----------|
| **User Enrollments** | Real-time (API handles) | 30 days | API database |
| **Application State** | N/A (stateless) | N/A | N/A |
| **Configuration** | Git | Forever | GitHub |
| **Logs** | Daily | 30 days | Log service |

### Rollback Procedures

```bash
# Vercel automatic rollback
# 1. Go to Vercel dashboard
# 2. Select previous deployment
# 3. Click "Promote to Production"

# Manual rollback via CLI
vercel rollback [deployment-url]

# Git-based rollback
git revert HEAD
git push origin main
# Triggers new deployment with reverted code
```

### Incident Response

```markdown
## Incident Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| **P1** | Service down | 15 minutes | App unreachable |
| **P2** | Major feature broken | 1 hour | Enrollment failing |
| **P3** | Minor feature broken | 4 hours | Dark mode not working |
| **P4** | Cosmetic issue | Next sprint | Button misaligned |

## Incident Checklist

1. [ ] Acknowledge incident in Slack
2. [ ] Assess severity level
3. [ ] Create incident channel if P1/P2
4. [ ] Investigate root cause
5. [ ] Implement fix or rollback
6. [ ] Verify fix in production
7. [ ] Update status page
8. [ ] Write post-mortem (P1/P2 only)
```

---

## Technical Debt Management

### Debt Classification

| Type | Example | Priority |
|------|---------|----------|
| **Architectural** | Monolith needs splitting | High |
| **Code Quality** | Duplicated logic | Medium |
| **Testing** | Missing E2E tests | Medium |
| **Documentation** | Outdated API docs | Low |
| **Tooling** | Old build system | Low |

### Debt Tracking

```typescript
// Use TODO comments with tickets
// TODO(DEMO-123): Refactor this to use shared hook
// FIXME(DEMO-456): This breaks on mobile Safari
// HACK(DEMO-789): Temporary workaround for API bug

// eslint-disable-next-line - requires comment
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- DEMO-101: API returns untyped response
```

### Debt Reduction Policy

```markdown
## Technical Debt Policy

1. **20% Rule**: Allocate 20% of each sprint to debt reduction
2. **No New Debt**: PRs adding debt require ticket creation
3. **Debt Reviews**: Monthly review of debt backlog
4. **Debt Metrics**: Track debt count and age in dashboard

## Debt Prioritization Matrix

| Impact / Effort | Low Effort | High Effort |
|-----------------|------------|-------------|
| **High Impact** | Do Now | Plan Sprint |
| **Low Impact** | Do When Free | Backlog |
```

---

## Implementation Plan

### Phase 1: Foundation (Days 1-2)

- [ ] Initialize Next.js 14 project with TypeScript
- [ ] Configure TailwindCSS and shadcn/ui
- [ ] Set up project structure
- [ ] Implement API client with mock mode
- [ ] Create layout components (Header, Sidebar, Footer)
- [ ] Implement settings store (Zustand)
- [ ] Add API health check

### Phase 2: Core Features (Days 3-5)

- [ ] Dashboard page with feature cards
- [ ] WebcamCapture component
- [ ] ImageUploader component
- [ ] Face Enrollment page
- [ ] Face Verification page with SimilarityGauge
- [ ] Face Search page with results table
- [ ] Liveness Detection page

### Phase 3: Advanced Analysis (Days 6-7)

- [ ] Quality Analysis page
- [ ] Demographics page
- [ ] Facial Landmarks page with canvas overlay
- [ ] Face Comparison page
- [ ] Batch Processing page

### Phase 4: Proctoring (Days 8-9)

- [ ] WebSocket manager
- [ ] Real-time video component
- [ ] Proctoring Session page
- [ ] Real-time Feed page
- [ ] Alert visualization

### Phase 5: Administration (Day 10)

- [ ] Admin Dashboard
- [ ] Webhooks management
- [ ] Configuration viewer
- [ ] API Explorer

### Phase 6: Polish & Testing (Days 11-12)

- [ ] Add Framer Motion animations
- [ ] Dark mode support
- [ ] Mobile responsiveness testing
- [ ] Write unit tests
- [ ] Write E2E tests
- [ ] Performance optimization

---

## Deployment Strategy

### Development

```bash
npm run dev
# Runs on http://localhost:3000
# API expected at http://localhost:8001
```

### Production Build

```bash
npm run build
npm run start
```

### Docker Deployment

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

### Environment Variables

```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
NEXT_PUBLIC_APP_NAME="Biometric Demo"
```

---

## Conclusion

This Next.js-based demo application provides:

1. **Professional Enterprise UI** - shadcn/ui components with polished styling
2. **Full Real-Time Support** - Native WebRTC and WebSocket integration
3. **Mobile-First Design** - Responsive across all devices
4. **Type-Safe Implementation** - Full TypeScript coverage
5. **Testable Architecture** - Comprehensive testing strategy
6. **Production-Ready** - Can evolve into actual client-facing application

The architecture follows software engineering best practices with SOLID principles, design patterns, and clean code standards suitable for a university engineering project.
