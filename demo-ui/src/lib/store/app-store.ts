import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface AppState {
  // Sidebar state
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  toggleSidebarCollapsed: () => void;
  setSidebarOpen: (open: boolean) => void;

  // API configuration
  apiUrl: string;
  setApiUrl: (url: string) => void;

  // Camera settings
  cameraFacingMode: 'user' | 'environment';
  setCameraFacingMode: (mode: 'user' | 'environment') => void;
  cameraResolution: 'hd' | 'fhd' | '4k';
  setCameraResolution: (resolution: 'hd' | 'fhd' | '4k') => void;

  // Feature flags
  features: {
    proctoring: boolean;
    batchProcessing: boolean;
    webhooks: boolean;
  };
  setFeatureEnabled: (feature: keyof AppState['features'], enabled: boolean) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Sidebar
      sidebarOpen: false,
      sidebarCollapsed: false,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      toggleSidebarCollapsed: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      // API
      apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001',
      setApiUrl: (url) => set({ apiUrl: url }),

      // Camera
      cameraFacingMode: 'user',
      setCameraFacingMode: (mode) => set({ cameraFacingMode: mode }),
      cameraResolution: 'hd',
      setCameraResolution: (resolution) => set({ cameraResolution: resolution }),

      // Features
      features: {
        proctoring: true,
        batchProcessing: true,
        webhooks: true,
      },
      setFeatureEnabled: (feature, enabled) =>
        set((state) => ({
          features: { ...state.features, [feature]: enabled },
        })),
    }),
    {
      name: 'biometric-demo-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        apiUrl: state.apiUrl,
        cameraFacingMode: state.cameraFacingMode,
        cameraResolution: state.cameraResolution,
      }),
    }
  )
);
