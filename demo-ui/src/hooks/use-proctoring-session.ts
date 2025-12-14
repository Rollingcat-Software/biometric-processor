import { useState, useCallback, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;

interface CreateSessionRequest {
  user_id: string;
  exam_id?: string;
  duration_minutes?: number;
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
  face_verified: boolean;
  liveness_score: number;
  risk_score: number;
  incidents: Incident[];
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
  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error('Failed to create session');
  return response.json();
}

async function startSessionApi(sessionId: string): Promise<Session> {
  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions/${sessionId}/start`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to start session');
  return response.json();
}

async function pauseSessionApi(sessionId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions/${sessionId}/pause`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to pause session');
}

async function resumeSessionApi(sessionId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions/${sessionId}/resume`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to resume session');
}

async function endSessionApi(sessionId: string): Promise<Session> {
  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions/${sessionId}/end`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to end session');
  return response.json();
}

async function submitFrameApi(sessionId: string, imageData: string): Promise<FrameResult> {
  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions/${sessionId}/frames`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: imageData }),
  });
  if (!response.ok) throw new Error('Failed to submit frame');
  return response.json();
}

async function fetchSessions(params?: { page?: number; page_size?: number }): Promise<SessionListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.page_size) searchParams.set('page_size', params.page_size.toString());

  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions?${searchParams}`);
  if (!response.ok) throw new Error('Failed to fetch sessions');
  return response.json();
}

async function fetchSession(sessionId: string): Promise<Session> {
  const response = await fetch(`${API_URL}/api/v1/proctoring/sessions/${sessionId}`);
  if (!response.ok) throw new Error('Failed to fetch session');
  return response.json();
}

export function useProctoringSession(options?: UseProctoringSessionOptions) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string>('none');
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const createMutation = useMutation({
    mutationFn: createSessionApi,
    onSuccess: (session) => {
      setSessionId(session.session_id);
      setSessionStatus('pending');
    },
  });

  const startMutation = useMutation({
    mutationFn: startSessionApi,
    onSuccess: () => {
      setSessionStatus('active');
    },
  });

  const endMutation = useMutation({
    mutationFn: endSessionApi,
    onSuccess: () => {
      setSessionStatus('completed');
      setSessionId(null);
    },
  });

  const createSession = useCallback(async (userId: string, examId?: string) => {
    return createMutation.mutateAsync({ user_id: userId, exam_id: examId });
  }, [createMutation]);

  const startSession = useCallback(async () => {
    if (!sessionId) throw new Error('No session to start');
    return startMutation.mutateAsync(sessionId);
  }, [sessionId, startMutation]);

  const pauseSession = useCallback(async () => {
    if (!sessionId) throw new Error('No session to pause');
    await pauseSessionApi(sessionId);
    setSessionStatus('paused');
  }, [sessionId]);

  const resumeSession = useCallback(async () => {
    if (!sessionId) throw new Error('No session to resume');
    await resumeSessionApi(sessionId);
    setSessionStatus('active');
  }, [sessionId]);

  const endSession = useCallback(async () => {
    if (!sessionId) throw new Error('No session to end');
    return endMutation.mutateAsync(sessionId);
  }, [sessionId, endMutation]);

  const submitFrame = useCallback(async (imageData: string) => {
    if (!sessionId) throw new Error('No active session');
    const result = await submitFrameApi(sessionId, imageData);

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
