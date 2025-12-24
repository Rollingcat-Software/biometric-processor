/**
 * API Response Types for Biometric Processor
 * Updated to match actual backend response formats
 */

// Base response wrapper
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  timestamp: string;
}

// Health check
export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  timestamp: string;
  services?: Record<string, ServiceHealth>;
}

export interface ServiceHealth {
  status: 'healthy' | 'unhealthy';
  latency_ms?: number;
  message?: string;
}

// Bounding box - used across multiple endpoints
export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

// Landmark point
export interface LandmarkPoint {
  x: number;
  y: number;
  z?: number;
  label?: string;
}

// Face detection - single face
export interface FaceDetectionResult {
  face_detected: boolean;
  confidence: number;
  quality_score: number;
  bounding_box: BoundingBox;
  face_id?: number;
}

// Multi-face detection
export interface MultiFaceDetectionResponse {
  face_count: number;
  faces: DetectedFace[];
  image_dimensions: {
    width: number;
    height: number;
  };
}

export interface DetectedFace {
  face_id: number;
  bounding_box: BoundingBox;
  confidence: number;
  quality_score: number;
  landmarks?: Array<{ x: number; y: number }>;
}

// Facial landmarks detection
export interface LandmarkDetectionResponse {
  landmarks: LandmarkPoint[];
  landmark_count: number;
  model: string;
  regions?: {
    left_eye?: LandmarkPoint[];
    right_eye?: LandmarkPoint[];
    nose?: LandmarkPoint[];
    mouth?: LandmarkPoint[];
    face_contour?: LandmarkPoint[];
    left_eyebrow?: LandmarkPoint[];
    right_eyebrow?: LandmarkPoint[];
  };
  head_pose?: {
    pitch: number;
    yaw: number;
    roll: number;
  };
}

// Face enrollment
export interface EnrollmentRequest {
  person_id: string;
  image: File | Blob;
  metadata?: Record<string, unknown>;
}

export interface EnrollmentResponse {
  user_id: string;
  embedding_id: string;
  success: boolean;
  message: string;
  quality_score?: number;
  created_at?: string;
}

// Face comparison/verification
export interface ComparisonRequest {
  image1: File | Blob;
  image2: File | Blob;
  threshold?: number;
}

export interface ComparisonResponse {
  match: boolean;
  similarity: number;
  distance: number;
  threshold: number;
  confidence: string;
  face1: {
    detected: boolean;
    quality_score: number;
    bounding_box: BoundingBox;
  };
  face2: {
    detected: boolean;
    quality_score: number;
    bounding_box: BoundingBox;
  };
  message: string;
}

// Face search
export interface SearchRequest {
  image: File | Blob;
  max_results?: number;
  threshold?: number;
}

export interface SearchResponse {
  matches: SearchMatch[];
  total_searched: number;
  query_embedding_id?: string;
}

export interface SearchMatch {
  user_id: string;
  similarity: number;
  embedding_id: string;
}

// Liveness detection
export interface LivenessRequest {
  image: File | Blob;
  challenge_type?: 'passive' | 'active';
}

export interface LivenessResponse {
  is_live: boolean;
  liveness_score: number;
  challenge?: string;
  challenge_completed?: boolean;
  message?: string;
}

export interface LivenessCheck {
  name: string;
  passed: boolean;
  score: number;
  message?: string;
}

// Quality analysis
export interface QualityAnalysisRequest {
  image: File | Blob;
}

export interface QualityAnalysisResponse {
  overall_score: number;
  passed: boolean;
  issues: QualityIssue[];
  metrics: QualityMetrics;
}

export interface QualityIssue {
  code: string;
  severity: string;
  message: string;
  value: number;
  threshold: number;
  suggestion: string;
}

export interface QualityMetrics {
  blur_score: number;
  brightness: number;
  face_size: number;
  face_angle: number;
  occlusion: number;
}

export type QualityGrade = 'excellent' | 'good' | 'acceptable' | 'poor' | 'failed';

// Demographics analysis
export interface DemographicsRequest {
  image: File | Blob;
}

export interface DemographicsResponse {
  age: {
    value: number;
    range: [number, number];
    confidence: number;
  };
  gender: {
    value: 'male' | 'female';
    confidence: number;
  };
  race: {
    dominant: string;
    confidence: number;
    all: Record<string, number>;
  } | null;
  emotion: {
    dominant: string;
    confidence: number;
    all: Record<string, number>;
  } | null;
}

export interface AgeEstimate {
  value: number;
  range: [number, number];
  confidence: number;
}

export interface GenderEstimate {
  value: 'male' | 'female';
  confidence: number;
}

export interface EmotionEstimate {
  dominant: string;
  all: Record<string, number>;
  confidence: number;
}

// Proctoring
export interface ProctoringSession {
  session_id: string;
  status: 'active' | 'paused' | 'ended';
  started_at: string;
  ended_at?: string;
  alerts: ProctoringAlert[];
}

export interface ProctoringAlert {
  id: string;
  type: ProctoringAlertType;
  timestamp: string;
  severity: 'low' | 'medium' | 'high';
  message: string;
  metadata?: Record<string, unknown>;
}

export type ProctoringAlertType =
  | 'no_face'
  | 'multiple_faces'
  | 'looking_away'
  | 'suspicious_movement'
  | 'different_person'
  | 'low_quality';

// Batch processing
export interface BatchRequest {
  files: File[];
  items?: string; // JSON string of items
  operation: 'enroll' | 'verify' | 'quality' | 'demographics';
  threshold?: number;
}

export interface BatchEnrollResponse {
  results: BatchEnrollResult[];
  total_processed: number;
  successful: number;
  failed: number;
  processing_time_ms: number;
}

export interface BatchEnrollResult {
  user_id: string;
  success: boolean;
  embedding_id?: string;
  error?: string;
}

export interface BatchVerifyResponse {
  results: BatchVerifyResult[];
  total_processed: number;
  matched: number;
  unmatched: number;
  failed: number;
  processing_time_ms: number;
}

export interface BatchVerifyResult {
  user_id: string;
  success: boolean;
  match?: boolean;
  similarity?: number;
  error?: string;
}

export interface BatchResult {
  index: number;
  success: boolean;
  user_id?: string;
  error?: string;
  similarity?: number;
  match?: boolean;
  embedding_id?: string;
}

export interface BatchError {
  index: number;
  error: string;
  details?: Record<string, unknown>;
}

// Webhooks
export interface Webhook {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
  last_triggered_at?: string;
}

export interface WebhookEvent {
  id: string;
  webhook_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: 'pending' | 'delivered' | 'failed';
  attempts: number;
  created_at: string;
}

// Error response
export interface ApiErrorResponse {
  error_code: string;
  message: string;
  detail?: string;
  errors?: Record<string, string[]>;
}
