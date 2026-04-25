'use client';

import { motion } from 'framer-motion';
import { CheckCircle2, XCircle, AlertTriangle, Info, Users, MapPin } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { formatPercent, toPercent } from '@/lib/utils/format';
import type { LiveAnalysisResult, AnalysisMode } from '@/hooks/use-live-camera-analysis';

interface AnalysisResultRendererProps {
  mode: AnalysisMode;
  result: any; // Can be LiveAnalysisResult or REST API result
  isLive?: boolean;
}

export function AnalysisResultRenderer({ mode, result, isLive = false }: AnalysisResultRendererProps) {
  if (!result) return null;

  // Live stream result wrapper
  if (isLive && 'frame_number' in result) {
    return (
      <div className="space-y-4">
        {/* Live indicator */}
        <div className="flex items-center justify-between rounded-lg bg-blue-50 p-3 text-sm dark:bg-blue-950/50">
          <Badge variant="default">Live Analysis</Badge>
          <span className="text-xs text-muted-foreground">
            Frame #{result.frame_number} • {result.processing_time_ms?.toFixed(0)}ms
          </span>
        </div>

        {/* Render actual result */}
        {renderModeSpecificResult(mode, result)}
      </div>
    );
  }

  // Static result
  return renderModeSpecificResult(mode, result);
}

function renderModeSpecificResult(mode: AnalysisMode, result: any) {
  switch (mode) {
    case 'face_detection':
      return renderFaceDetection(result);
    case 'quality':
      return renderQuality(result);
    case 'demographics':
      return renderDemographics(result);
    case 'liveness':
      return renderLiveness(result);
    case 'enrollment_ready':
      return renderEnrollmentReady(result);
    case 'verification':
      return renderVerification(result);
    case 'search':
      return renderSearch(result);
    case 'landmarks':
      return renderLandmarks(result);
    case 'full':
      return renderFullAnalysis(result);
    default:
      return renderGeneric(result);
  }
}

// Face Detection
function renderFaceDetection(result: any) {
  const faceData = result.face || result;
  const detected = faceData.detected !== false;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div
        className={`flex items-center gap-3 rounded-lg p-4 ${
          detected ? 'bg-green-500/10' : 'bg-red-500/10'
        }`}
      >
        {detected ? (
          <CheckCircle2 className="h-8 w-8 text-green-600" />
        ) : (
          <XCircle className="h-8 w-8 text-red-600" />
        )}
        <div>
          <p className={`text-lg font-semibold ${detected ? 'text-green-600' : 'text-red-600'}`}>
            {detected ? 'Face Detected' : 'No Face Detected'}
          </p>
          {detected && faceData.confidence && (
            <p className="text-sm text-muted-foreground">
              Confidence: {formatPercent(faceData.confidence)}
            </p>
          )}
        </div>
      </div>

      {detected && faceData.bbox && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg border p-3">
            <p className="text-muted-foreground">Position</p>
            <p className="font-mono">
              ({faceData.bbox.x}, {faceData.bbox.y})
            </p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-muted-foreground">Size</p>
            <p className="font-mono">
              {faceData.bbox.width} × {faceData.bbox.height}
            </p>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// Quality Analysis
function renderQuality(result: any) {
  const qualityData = result.quality || result;
  const score = qualityData.overall_score || qualityData.score || 0;

  const getGrade = (s: number) => {
    if (s >= 0.9) return { label: 'Excellent', color: 'text-green-600', bg: 'bg-green-500/10' };
    if (s >= 0.75) return { label: 'Good', color: 'text-blue-600', bg: 'bg-blue-500/10' };
    if (s >= 0.6) return { label: 'Acceptable', color: 'text-yellow-600', bg: 'bg-yellow-500/10' };
    if (s >= 0.4) return { label: 'Poor', color: 'text-orange-600', bg: 'bg-orange-500/10' };
    return { label: 'Failed', color: 'text-red-600', bg: 'bg-red-500/10' };
  };

  const grade = getGrade(score);

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className={`rounded-lg p-4 ${grade.bg}`}>
        <p className={`text-2xl font-bold ${grade.color}`}>{formatPercent(score)}</p>
        <p className="text-sm text-muted-foreground">{grade.label} Quality</p>
      </div>

      {qualityData.metrics && (
        <div className="space-y-3">
          <p className="text-sm font-medium">Quality Metrics</p>
          {Object.entries(qualityData.metrics).map(([key, value]: [string, any]) => (
            <div key={key} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="capitalize">{key.replace(/_/g, ' ')}</span>
                <span className="font-mono">{formatPercent(value, 0)}</span>
              </div>
              <Progress value={toPercent(value)} className="h-2" />
            </div>
          ))}
        </div>
      )}

      {qualityData.recommendation && (
        <div className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
          <span>{qualityData.recommendation}</span>
        </div>
      )}
    </motion.div>
  );
}

// Demographics
function renderDemographics(result: any) {
  const demo = result.demographics || result;

  // Extract values - handle both nested objects and flat values from API
  const ageValue = typeof demo.age === 'object' ? demo.age?.value : demo.age;
  const ageRange = typeof demo.age === 'object' ? demo.age?.range : demo.age_range;
  const ageConfidence = typeof demo.age === 'object' ? demo.age?.confidence : null;

  const genderValue = typeof demo.gender === 'object' ? demo.gender?.value : demo.gender;
  const genderConfidence = typeof demo.gender === 'object' ? demo.gender?.confidence : demo.gender_confidence;

  const emotionValue = typeof demo.emotion === 'object' ? demo.emotion?.dominant : demo.emotion;
  const emotionScores = typeof demo.emotion === 'object' ? demo.emotion?.all : demo.emotion_scores;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {ageValue !== null && ageValue !== undefined && (
          <div className="rounded-lg border bg-gradient-to-br from-blue-500/10 to-blue-500/5 p-4">
            <p className="text-sm text-muted-foreground">Age</p>
            <p className="text-3xl font-bold text-blue-600">{ageValue}</p>
            {ageRange && (
              <p className="text-xs text-muted-foreground">
                Range: {Array.isArray(ageRange) ? `${ageRange[0]}-${ageRange[1]}` : ageRange}
              </p>
            )}
            {ageConfidence && (
              <p className="text-xs text-muted-foreground">Confidence: {formatPercent(ageConfidence)}</p>
            )}
          </div>
        )}

        {genderValue && (
          <div className="rounded-lg border bg-gradient-to-br from-purple-500/10 to-purple-500/5 p-4">
            <p className="text-sm text-muted-foreground">Gender</p>
            <p className="text-3xl font-bold capitalize text-purple-600">{genderValue}</p>
            {genderConfidence && (
              <p className="text-xs text-muted-foreground">{formatPercent(genderConfidence)}</p>
            )}
          </div>
        )}

        {emotionValue && (
          <div className="rounded-lg border bg-gradient-to-br from-pink-500/10 to-pink-500/5 p-4 sm:col-span-2">
            <p className="text-sm text-muted-foreground">Dominant Emotion</p>
            <p className="text-3xl font-bold capitalize text-pink-600">{emotionValue}</p>
          </div>
        )}
      </div>

      {emotionScores && Object.keys(emotionScores).length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">All Emotions</p>
          {Object.entries(emotionScores).map(([emotion, score]: [string, any]) => (
            <div key={emotion} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="capitalize">{emotion}</span>
                <span className="font-mono text-xs">{formatPercent(score, 0)}</span>
              </div>
              <Progress value={toPercent(score)} className="h-1.5" />
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// Liveness Detection
function renderLiveness(result: any) {
  const liveness = result.liveness || result;
  const isLive = liveness.is_live;
  const score = liveness.score ?? liveness.liveness_score ?? 0;
  const confidence = liveness.confidence ?? (score > 1 ? score / 100 : score);

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className={`rounded-lg p-6 ${isLive ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
        <p className={`text-3xl font-bold ${isLive ? 'text-green-600' : 'text-red-600'}`}>
          {isLive ? '✓ Live Person' : '✗ Spoof Detected'}
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="space-y-1 rounded-lg border bg-background/60 p-3">
            <p className="text-xs text-muted-foreground">Liveness Score</p>
            <p className="font-semibold">{formatPercent(score)}</p>
            <Progress value={toPercent(score)} className="h-1.5" />
          </div>
          <div className="space-y-1 rounded-lg border bg-background/60 p-3">
            <p className="text-xs text-muted-foreground">Decision Confidence</p>
            <p className="font-semibold">{formatPercent(confidence)}</p>
            <Progress value={toPercent(confidence)} className="h-1.5" />
          </div>
        </div>
        {liveness.challenge && (
          <p className="mt-2 text-xs text-muted-foreground">Challenge: {liveness.challenge}</p>
        )}
        {liveness.method && (
          <p className="text-xs text-muted-foreground">Method: {liveness.method}</p>
        )}
      </div>

      {liveness.checks && Object.keys(liveness.checks).length > 0 && (
        <div className="space-y-2 rounded-lg border p-3">
          <p className="text-sm font-medium">Liveness Checks</p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(liveness.checks).map(([check, passed]: [string, any]) => (
              <div key={check} className="flex items-center gap-2">
                {passed ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                <span className="capitalize">{check}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

// Enrollment Ready
function renderEnrollmentReady(result: any) {
  const enrollment = result.enrollment_ready || result;
  const ready = enrollment.ready || enrollment.is_ready;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className={`rounded-lg p-6 ${ready ? 'bg-green-500/10' : 'bg-orange-500/10'}`}>
        <p className={`text-2xl font-bold ${ready ? 'text-green-600' : 'text-orange-600'}`}>
          {ready ? '✅ Ready for Enrollment' : '⚠️ Not Ready Yet'}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div className={`rounded-lg border p-3 ${enrollment.face_detected ? 'bg-green-50 dark:bg-green-950/20' : ''}`}>
          <p className="text-muted-foreground">Face</p>
          <p className="font-semibold">{enrollment.face_detected ? '✓' : '✗'}</p>
        </div>
        <div className={`rounded-lg border p-3 ${enrollment.quality_met ? 'bg-green-50 dark:bg-green-950/20' : ''}`}>
          <p className="text-muted-foreground">Quality</p>
          <p className="font-semibold">{enrollment.quality_met ? '✓' : '✗'}</p>
        </div>
        <div className={`rounded-lg border p-3 ${enrollment.liveness_met ? 'bg-green-50 dark:bg-green-950/20' : ''}`}>
          <p className="text-muted-foreground">Liveness</p>
          <p className="font-semibold">{enrollment.liveness_met ? '✓' : '✗'}</p>
        </div>
      </div>

      {enrollment.recommendation && (
        <div className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
          <span>{enrollment.recommendation}</span>
        </div>
      )}
    </motion.div>
  );
}

// Verification
function renderVerification(result: any) {
  const verification = result.verification || result;
  const match = verification.match;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className={`rounded-lg p-6 ${match ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
        <p className={`text-3xl font-bold ${match ? 'text-green-600' : 'text-red-600'}`}>
          {match ? '✓ Identity Verified' : '✗ No Match'}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Similarity: {formatPercent(verification.similarity || verification.confidence)}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border p-3">
          <p className="text-sm text-muted-foreground">User ID</p>
          <p className="font-mono text-sm">{verification.user_id}</p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-sm text-muted-foreground">Threshold</p>
          <p className="font-mono text-sm">{formatPercent(verification.threshold)}</p>
        </div>
      </div>
    </motion.div>
  );
}

// Search
function renderSearch(result: any) {
  const search = result.search || result;
  const found = search.found;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className={`rounded-lg p-6 ${found ? 'bg-green-500/10' : 'bg-orange-500/10'}`}>
        <p className={`text-2xl font-bold ${found ? 'text-green-600' : 'text-orange-600'}`}>
          {found ? '✓ Match Found' : 'No Match'}
        </p>
        {found && (search.best_match?.user_id ?? search.user_id) && (
          <p className="mt-2 text-sm text-muted-foreground">User: {(search.best_match?.user_id ?? search.user_id)}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg border p-3">
          <p className="text-muted-foreground">Confidence</p>
          <p className="font-mono">{formatPercent(search.best_match?.confidence ?? search.confidence)}</p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-muted-foreground">Candidates</p>
          <p className="font-mono">{search.num_candidates || search.total_searched || 0}</p>
        </div>
      </div>
    </motion.div>
  );
}

// Landmarks
function renderLandmarks(result: any) {
  const landmarks = result.landmarks || result;
  const count = landmarks.num_landmarks || landmarks.landmark_count || 0;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border bg-gradient-to-br from-indigo-500/10 to-indigo-500/5 p-4">
          <p className="text-sm text-muted-foreground">Landmarks</p>
          <p className="text-4xl font-bold text-indigo-600">{count}</p>
        </div>
        <div className="rounded-lg border bg-gradient-to-br from-purple-500/10 to-purple-500/5 p-4">
          <p className="text-sm text-muted-foreground">Confidence</p>
          <p className="text-4xl font-bold text-purple-600">
            {formatPercent(landmarks.confidence, 0)}
          </p>
        </div>
      </div>

      {landmarks.landmarks && typeof landmarks.landmarks === 'object' && (
        <div className="rounded-lg border p-3">
          <p className="mb-2 text-sm font-medium">Detected Points</p>
          <div className="flex flex-wrap gap-2">
            {Object.keys(landmarks.landmarks).slice(0, 10).map((key) => (
              <Badge key={key} variant="outline" className="font-mono text-xs">
                <MapPin className="mr-1 h-3 w-3" />
                {key}
              </Badge>
            ))}
            {Object.keys(landmarks.landmarks).length > 10 && (
              <Badge variant="secondary" className="text-xs">
                +{Object.keys(landmarks.landmarks).length - 10} more
              </Badge>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}

// Full Analysis
function renderFullAnalysis(result: any) {
  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
      <div className="rounded-lg bg-gradient-to-r from-purple-500/10 to-pink-500/10 p-4">
        <p className="text-lg font-bold">Full Analysis Results</p>
        <p className="text-sm text-muted-foreground">Comprehensive biometric analysis</p>
      </div>

      {result.quality && (
        <div>
          <p className="mb-2 text-sm font-medium">Quality Assessment</p>
          {renderQuality(result)}
        </div>
      )}

      {result.liveness && (
        <div>
          <p className="mb-2 text-sm font-medium">Liveness Detection</p>
          {renderLiveness(result)}
        </div>
      )}

      {result.demographics && (
        <div>
          <p className="mb-2 text-sm font-medium">Demographics</p>
          {renderDemographics(result)}
        </div>
      )}
    </motion.div>
  );
}

// Generic fallback
function renderGeneric(result: any) {
  return (
    <pre className="max-h-96 overflow-auto rounded-lg bg-muted p-4 text-xs">
      {JSON.stringify(result, null, 2)}
    </pre>
  );
}
