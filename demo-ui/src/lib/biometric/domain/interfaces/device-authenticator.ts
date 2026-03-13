/**
 * Port for device-native biometric authentication (WebAuthn/FIDO2).
 *
 * Replaces fingerprint/voice stubs with real device authentication.
 * Abstracts the WebAuthn API so use cases don't depend on browser APIs.
 */

import type {
  DeviceAuthParams,
  DeviceAuthResult,
  DeviceCredential,
  DeviceRegisterParams,
} from '../types';

export interface IDeviceAuthenticator {
  /** Check if device supports biometric authentication. */
  isAvailable(): Promise<boolean>;

  /** Register a new credential (enrollment equivalent). */
  register(params: DeviceRegisterParams): Promise<DeviceCredential>;

  /** Authenticate with existing credential (verification equivalent). */
  authenticate(params: DeviceAuthParams): Promise<DeviceAuthResult>;

  /** Remove a stored credential. */
  removeCredential(credentialId: string): Promise<void>;
}
