import { useState, useCallback, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.LONG;

// Default tenant ID for demo purposes
const DEFAULT_TENANT_ID = 'demo-tenant';

interface CreateSessionRequest {
  user_id: string;
  exam_id: string; // Required by backend
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

interface Session {
  session_id: string;
  user_id: string;
  exam_id?: string;
  status: 'pending' | 'active' | 'paused' | 'completed' | 'terminated';
  started_at?: string;
  ended_at?: string;
  created_at: string;
}

interface Incident {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high';
  timestamp: string;
  message: string;
}

interface FrameResult {
  session_id: string;
  frame_number: number;
  face_detected: boolean;
  face_verified: boolean;
  face_matched?: boolean;
  liveness_score?: number;
  risk_score: number;
  incidents_created?: number;
  incidents?: Incident[];
  processing_time_ms?: number;
}

interface SessionListResponse {
  sessions: Session[];
  total: number;
  page: number;
  page_size: number;
}

interface UseProctoringSessionOptions {
  onIncident?: (incident: Incident) => void;
  onFrameResult?: (result: FrameResult) => void;
}

async function createSessionApi(request: CreateSessionRequest): Promise<Session> {
  return apiClient.post<Session>('/api/v1/proctoring/sessions', request, {
    headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID }
  });
}

async function startSessionApi(sessionId: string, baselineImage?: string): Promise<Session> {
  console.log('Starting session:', sessionId, baselineImage ? '(with baseline image)' : '(no baseline)');

  const body = baselineImage ? { baseline_image_base64: baselineImage } : {};
  const response = await apiClient.post<Session>(
    `/api/v1/proctoring/sessions/${sessionId}/start`,
    body,
    {
      headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID },
      timeout: 30000
    }
  );

  console.log('Start session response received');
  return response;
}

async function pauseSessionApi(sessionId: string): Promise<void> {
  console.log('pauseSessionApi called for session:', sessionId);
  await apiClient.post(`/api/v1/proctoring/sessions/${sessionId}/pause`, {}, {
    headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID }
  });
  console.log('pauseSessionApi success');
}

async function resumeSessionApi(sessionId: string): Promise<void> {
  await apiClient.post(`/api/v1/proctoring/sessions/${sessionId}/resume`, {}, {
    headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID }
  });
}

async function endSessionApi(sessionId: string): Promise<Session> {
  console.log('endSessionApi called for session:', sessionId);
  const result = await apiClient.post<Session>(`/api/v1/proctoring/sessions/${sessionId}/end`, {}, {
    headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID }
  });
  console.log('endSessionApi success:', result);
  return result;
}

async function submitFrameApi(
  sessionId: string,
  frameBase64: string,
  frameNumber: number
): Promise<FrameResult> {
  return apiClient.post<FrameResult>(
    `/api/v1/proctoring/sessions/${sessionId}/frames`,
    {
      frame_base64: frameBase64,
      frame_number: frameNumber,
    },
    {
      headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID },
      timeout: REQUEST_TIMEOUT
    }
  );
}

async function fetchSessions(params?: { page?: number; page_size?: number }): Promise<SessionListResponse> {
  return apiClient.get<SessionListResponse>('/api/v1/proctoring/sessions', {
    params,
    headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID }
  });
}

async function fetchSession(sessionId: string): Promise<Session> {
  return apiClient.get<Session>(`/api/v1/proctoring/sessions/${sessionId}`, {
    headers: { 'X-Tenant-ID': DEFAULT_TENANT_ID }
  });
}

export function useProctoringSession(options?: UseProctoringSessionOptions) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string>('none');
  const frameNumberRef = useRef(0);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const createMutation = useMutation({
    mutationFn: createSessionApi,
    onSuccess: (session) => {
      setSessionId(session.session_id);
      setSessionStatus('pending');
      frameNumberRef.current = 0; // Reset frame counter
    },
    onError: (error) => {
      console.error('Create session failed:', error);
    },
  });

  const startMutation = useMutation({
    mutationFn: ({ sessionId, baselineImage }: { sessionId: string; baselineImage?: string }) =>
      startSessionApi(sessionId, baselineImage),
    onSuccess: () => {
      setSessionStatus('active');
    },
    onError: (error) => {
      console.error('Start session failed:', error);
    },
  });

  const endMutation = useMutation({
    mutationFn: endSessionApi,
    onSuccess: () => {
      setSessionStatus('completed');
      setSessionId(null);
      frameNumberRef.current = 0;
    },
    onError: (error) => {
      console.error('End session failed:', error);
    },
  });

  const createSession = useCallback(async (userId: string, examId: string) => {
    return createMutation.mutateAsync({ user_id: userId, exam_id: examId });
  }, [createMutation]);

  const startSession = useCallback(async (baselineImage?: string) => {
    if (!sessionId) throw new Error('No session to start');
    return startMutation.mutateAsync({ sessionId, baselineImage });
  }, [sessionId, startMutation]);

  const pauseSession = useCallback(async () => {
    console.log('pauseSession hook called, sessionId:', sessionId);
    if (!sessionId) throw new Error('No session to pause');
    await pauseSessionApi(sessionId);
    console.log('Setting status to paused');
    setSessionStatus('paused');
  }, [sessionId]);

  const resumeSession = useCallback(async () => {
    if (!sessionId) throw new Error('No session to resume');
    await resumeSessionApi(sessionId);
    setSessionStatus('active');
  }, [sessionId]);

  const endSession = useCallback(async () => {
    console.log('endSession hook called, sessionId:', sessionId);
    if (!sessionId) throw new Error('No session to end');
    return endMutation.mutateAsync(sessionId);
  }, [sessionId, endMutation]);

  const submitFrame = useCallback(async (imageData: string) => {
    if (!sessionId) throw new Error('No active session');
    const frameNumber = frameNumberRef.current++;
    const result = await submitFrameApi(sessionId, imageData, frameNumber);

    // Handle incidents
    if (result.incidents && optionsRef.current?.onIncident) {
      result.incidents.forEach(incident => {
        optionsRef.current?.onIncident?.(incident);
      });
    }

    // Handle frame result
    if (optionsRef.current?.onFrameResult) {
      optionsRef.current.onFrameResult(result);
    }

    return result;
  }, [sessionId]);

  return {
    sessionId,
    sessionStatus,
    createSession,
    startSession,
    pauseSession,
    resumeSession,
    endSession,
    submitFrame,
    isCreating: createMutation.isPending,
    isStarting: startMutation.isPending,
    isEnding: endMutation.isPending,
    createError: createMutation.error,
    startError: startMutation.error,
    endError: endMutation.error,
  };
}

// Keep these for other pages that need session listing
export function useProctoringSessionList(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ['proctoring-sessions', params],
    queryFn: () => fetchSessions(params),
  });
}

export function useProctoringSessionById(sessionId: string | null) {
  return useQuery({
    queryKey: ['proctoring-session', sessionId],
    queryFn: () => fetchSession(sessionId!),
    enabled: !!sessionId,
  });
}
