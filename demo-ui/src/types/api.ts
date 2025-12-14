/**
 * API Response Types for Biometric Processor
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

// Face detection
export interface FaceDetectionResult {
  face_id: string;
  bounding_box: BoundingBox;
  confidence: number;
  landmarks?: FacialLandmarks;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface FacialLandmarks {
  points: LandmarkPoint[];
  model: string;
}

export interface LandmarkPoint {
  x: number;
  y: number;
  z?: number;
  label?: string;
}

// Face enrollment
export interface EnrollmentRequest {
  person_id: string;
  image: File | Blob;
  metadata?: Record<string, unknown>;
}

export interface EnrollmentResponse {
  success: boolean;
  face_id: string;
  person_id: string;
  quality_score: number;
  embedding_id: string;
  message?: string;
}

// Face verification
export interface VerificationRequest {
  image1: File | Blob;
  image2: File | Blob;
  threshold?: number;
}

export interface VerificationResponse {
  match: boolean;
  similarity: number;
  threshold: number;
  processing_time_ms: number;
  face1: FaceDetectionResult;
  face2: FaceDetectionResult;
}

// Face search
export interface SearchRequest {
  image: File | Blob;
  max_results?: number;
  threshold?: number;
}

export interface SearchResponse {
  matches: SearchMatch[];
  processing_time_ms: number;
  query_face: FaceDetectionResult;
}

export interface SearchMatch {
  person_id: string;
  face_id: string;
  similarity: number;
  metadata?: Record<string, unknown>;
}

// Liveness detection
export interface LivenessRequest {
  image: File | Blob;
  challenge_type?: 'passive' | 'active';
}

export interface LivenessResponse {
  is_live: boolean;
  liveness_score: number;
  spoof_type?: string;
  processing_time_ms: number;
  checks: LivenessCheck[];
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
  grade: QualityGrade;
  metrics: QualityMetrics;
  recommendations?: string[];
}

export type QualityGrade = 'excellent' | 'good' | 'acceptable' | 'poor' | 'failed';

export interface QualityMetrics {
  brightness: number;
  contrast: number;
  sharpness: number;
  pose_deviation: number;
  face_size: number;
  occlusion: number;
  expression_neutrality: number;
}

// Demographics
export interface DemographicsRequest {
  image: File | Blob;
}

export interface DemographicsResponse {
  age: AgeEstimate;
  gender: GenderEstimate;
  emotion: EmotionEstimate;
  processing_time_ms: number;
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
  scores: Record<string, number>;
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
  images: File[];
  operation: 'enroll' | 'verify' | 'quality' | 'demographics';
  options?: Record<string, unknown>;
}

export interface BatchResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  total_items: number;
  processed_items: number;
  results?: BatchResult[];
  errors?: BatchError[];
}

export interface BatchResult {
  index: number;
  success: boolean;
  result: unknown;
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
