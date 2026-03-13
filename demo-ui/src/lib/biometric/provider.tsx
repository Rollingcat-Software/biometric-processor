/**
 * React context provider for the biometric DI container.
 *
 * Initializes the container once and provides it to all child components.
 * Handles cleanup on unmount (model disposal).
 *
 * Usage:
 *   <BiometricProvider config={{ qualityThreshold: 60 }}>
 *     <App />
 *   </BiometricProvider>
 */

'use client';

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';
import type { BiometricConfig } from './domain/types';
import { createBiometricContainer, type BiometricContainer } from './container';

const BiometricContext = createContext<BiometricContainer | null>(null);

export interface BiometricProviderProps {
  config?: Partial<BiometricConfig>;
  children: ReactNode;
}

export function BiometricProvider({ config, children }: BiometricProviderProps) {
  const container = useMemo(
    () => createBiometricContainer(config),
    // Config is an object — serialize to prevent unnecessary re-creation
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(config)],
  );

  useEffect(() => {
    return () => {
      container.dispose();
    };
  }, [container]);

  return (
    <BiometricContext.Provider value={container}>
      {children}
    </BiometricContext.Provider>
  );
}

/**
 * Access the biometric DI container from any child component.
 *
 * @throws Error if used outside of BiometricProvider
 */
export function useBiometricContainer(): BiometricContainer {
  const ctx = useContext(BiometricContext);
  if (!ctx) {
    throw new Error(
      'useBiometricContainer must be used within a <BiometricProvider>. ' +
      'Wrap your component tree with <BiometricProvider> to provide the biometric container.',
    );
  }
  return ctx;
}
