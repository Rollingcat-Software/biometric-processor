# Live Analysis Performance Analysis

This document provides performance characteristics and recommendations for the live camera analysis features.

## Overview

The live analysis system processes camera frames in real-time using WebSocket communication. Performance depends on:

1. **Processing complexity** - ML model inference time
2. **Image resolution** - Higher resolution = slower processing
3. **Hardware capabilities** - CPU/GPU performance
4. **Database size** - Affects verification/search modes
5. **Network overhead** - WebSocket latency (~30-50ms)

## Performance Characteristics by Mode

### 1. Face Detection (`face_detection`)

**Primary Operation**: Detect face bounding box and landmarks

**Typical Performance**:
- **Processing Time**: 10-30ms
- **Max Theoretical FPS**: 30-100
- **Recommended FPS**: 15-30
- **Use Case**: Real-time face tracking

**Factors**:
- Very fast with MediaPipe
- Scales well with resolution
- Minimal variance

**Recommended Settings**:
```typescript
{
  mode: 'face_detection',
  fps: 20,
  frame_skip: 0,
  resolution: '720p' // or '1080p'
}
```

---

### 2. Quality Analysis (`quality`)

**Primary Operation**: Assess image quality (blur, brightness, sharpness, centering)

**Typical Performance**:
- **Processing Time**: 30-60ms
- **Max Theoretical FPS**: 15-30
- **Recommended FPS**: 10-15
- **Use Case**: Live quality feedback during enrollment

**Factors**:
- Fast processing
- Includes face detection + quality metrics
- Slight overhead from multiple checks

**Recommended Settings**:
```typescript
{
  mode: 'quality',
  fps: 12,
  frame_skip: 0,
  resolution: '720p',
  quality_threshold: 70.0
}
```

---

### 3. Demographics (`demographics`)

**Primary Operation**: Estimate age, gender, emotion

**Typical Performance**:
- **Processing Time**: 150-300ms
- **Max Theoretical FPS**: 3-7
- **Recommended FPS**: 2-5
- **Use Case**: Periodic demographic analysis

**Factors**:
- Slower due to DeepFace processing
- High CPU/GPU usage
- Can have significant variance

**Recommended Settings**:
```typescript
{
  mode: 'demographics',
  fps: 3,
  frame_skip: 1, // Process every other frame
  resolution: '720p' // Lower resolution helps
}
```

**Note**: Consider implementing caching or processing every Nth frame only.

---

### 4. Liveness Detection (`liveness`)

**Primary Operation**: Detect if face is real person or spoof/photo

**Typical Performance**:
- **Processing Time**: 80-150ms
- **Max Theoretical FPS**: 7-12
- **Recommended FPS**: 5-10
- **Use Case**: Real-time spoof detection

**Factors**:
- Moderate complexity
- Depends on liveness method (passive vs active)
- Texture and depth analysis

**Recommended Settings**:
```typescript
{
  mode: 'liveness',
  fps: 8,
  frame_skip: 0,
  resolution: '720p'
}
```

---

### 5. Enrollment Ready (`enrollment_ready`)

**Primary Operation**: Combined quality + liveness check

**Typical Performance**:
- **Processing Time**: 50-100ms
- **Max Theoretical FPS**: 10-20
- **Recommended FPS**: 8-12
- **Use Case**: Live guidance during enrollment

**Factors**:
- Combines quality and liveness
- Provides real-time feedback
- Critical for user experience

**Recommended Settings**:
```typescript
{
  mode: 'enrollment_ready',
  fps: 10,
  frame_skip: 0,
  resolution: '720p',
  quality_threshold: 75.0
}
```

---

### 6. Verification (`verification`)

**Primary Operation**: 1:1 face matching against enrolled user

**Typical Performance**:
- **Processing Time**: 40-80ms
- **Max Theoretical FPS**: 12-25
- **Recommended FPS**: 8-15
- **Use Case**: Real-time identity verification

**Factors**:
- Embedding extraction + similarity calculation
- Database lookup (single user)
- Fast with indexed database

**Recommended Settings**:
```typescript
{
  mode: 'verification',
  fps: 12,
  frame_skip: 0,
  resolution: '720p',
  user_id: 'user_123'
}
```

---

### 7. Search (`search`)

**Primary Operation**: 1:N face identification in database

**Typical Performance**:
- **Processing Time**: 100-500+ms (depends on database size)
- **Max Theoretical FPS**: 2-10
- **Recommended FPS**: 2-5
- **Use Case**: Identify person from database

**Factors**:
- **HIGHLY** dependent on database size
- Embedding extraction + similarity search
- Scales with number of enrolled users
  - 100 users: ~100ms
  - 1,000 users: ~200ms
  - 10,000 users: ~500ms+
  - 100,000+ users: Consider vector database

**Recommended Settings**:
```typescript
{
  mode: 'search',
  fps: 3,
  frame_skip: 1,
  resolution: '720p',
  // For large databases
  tenant_id: 'specific_tenant' // Limit search scope
}
```

**Optimization Tips**:
- Use tenant isolation to reduce search space
- Implement vector database (FAISS, Annoy) for large scale
- Consider limiting top_k results
- Use approximate nearest neighbor (ANN) algorithms

---

### 8. Landmarks (`landmarks`)

**Primary Operation**: Detect 468 facial landmark points

**Typical Performance**:
- **Processing Time**: 20-50ms
- **Max Theoretical FPS**: 20-50
- **Recommended FPS**: 10-20
- **Use Case**: Real-time facial landmark tracking

**Factors**:
- Fast with MediaPipe
- Returns detailed coordinate data
- Good for real-time applications

**Recommended Settings**:
```typescript
{
  mode: 'landmarks',
  fps: 15,
  frame_skip: 0,
  resolution: '720p'
}
```

---

### 9. Full Analysis (`full`)

**Primary Operation**: All analyses combined

**Typical Performance**:
- **Processing Time**: 300-600ms
- **Max Theoretical FPS**: 1.5-3
- **Recommended FPS**: 1-2
- **Use Case**: Comprehensive analysis (batch mode)

**Factors**:
- Combines all modes
- Very slow
- Not recommended for real-time

**Recommended Settings**:
```typescript
{
  mode: 'full',
  fps: 1,
  frame_skip: 2, // Process every 3rd frame
  resolution: '480p' // Lower resolution recommended
}
```

---

## Performance Summary Table

| Mode | Avg Time (ms) | Max FPS (Theory) | Recommended FPS | Frame Skip | Resolution | Use Case |
|------|---------------|------------------|-----------------|------------|------------|----------|
| Face Detection | 10-30 | 30-100 | 15-30 | 0 | 720p-1080p | Real-time tracking |
| Quality | 30-60 | 15-30 | 10-15 | 0 | 720p | Live feedback |
| Demographics | 150-300 | 3-7 | 2-5 | 1 | 720p | Periodic analysis |
| Liveness | 80-150 | 7-12 | 5-10 | 0 | 720p | Spoof detection |
| Enrollment Ready | 50-100 | 10-20 | 8-12 | 0 | 720p | Live guidance |
| Verification | 40-80 | 12-25 | 8-15 | 0 | 720p | 1:1 matching |
| Search | 100-500+ | 2-10 | 2-5 | 1 | 720p | 1:N search |
| Landmarks | 20-50 | 20-50 | 10-20 | 0 | 720p | Landmark tracking |
| Full Analysis | 300-600 | 1.5-3 | 1-2 | 2 | 480p | Batch analysis |

---

## Implementation Recommendations

### 1. Default FPS Configuration

Update `LiveCameraStream` component with these defaults:

```typescript
const DEFAULT_FPS: Record<AnalysisMode, number> = {
  face_detection: 20,
  quality: 12,
  demographics: 3,
  liveness: 8,
  enrollment_ready: 10,
  verification: 12,
  search: 3,
  landmarks: 15,
  full: 1,
};
```

### 2. Adaptive FPS

Implement adaptive FPS based on processing time:

```typescript
const adaptFPS = (processingTimeMs: number, currentFPS: number) => {
  const targetProcessingRatio = 0.7; // Use 70% of available time
  const frameTimeMs = 1000 / currentFPS;

  if (processingTimeMs > frameTimeMs * targetProcessingRatio) {
    // Processing too slow, reduce FPS
    return Math.max(1, Math.floor(1000 / (processingTimeMs * 1.5)));
  } else if (processingTimeMs < frameTimeMs * 0.5) {
    // Processing fast, can increase FPS
    return Math.min(30, currentFPS + 2);
  }

  return currentFPS;
};
```

### 3. Resolution Guidelines

**For Mobile Devices**:
- Use 480p (640x480) for slower modes (demographics, search)
- Use 720p (1280x720) for balanced modes
- Avoid 1080p+ on mobile

**For Desktop**:
- Use 720p as default
- Use 1080p for fast modes (face detection, landmarks)
- Use 480p-720p for slow modes

### 4. Frame Skip Strategy

```typescript
const FRAME_SKIP_CONFIG: Record<AnalysisMode, number> = {
  face_detection: 0,    // No skip - need smooth tracking
  quality: 0,           // No skip - immediate feedback
  demographics: 1,      // Skip 1 (process every 2nd frame)
  liveness: 0,          // No skip - security critical
  enrollment_ready: 0,  // No skip - UX critical
  verification: 0,      // No skip - quick enough
  search: 1,            // Skip 1 (process every 2nd frame)
  landmarks: 0,         // No skip - need smooth tracking
  full: 2,              // Skip 2 (process every 3rd frame)
};
```

### 5. User Experience Guidelines

**Excellent (15+ FPS)**:
- Smooth, real-time feedback
- No perceptible lag
- Good for critical UX flows

**Good (8-15 FPS)**:
- Slight delay, but responsive
- Acceptable for most use cases
- Balance between performance and UX

**Acceptable (5-8 FPS)**:
- Noticeable delay
- Use for non-critical features
- Add progress indicators

**Poor (<5 FPS)**:
- Significant lag
- Only for batch/background processing
- Show clear processing indicators

---

## Hardware Considerations

### CPU-only Processing

**Entry-level (2-4 cores)**:
- Multiply processing times by 2-3x
- Use frame_skip aggressively
- Reduce resolution to 480p

**Mid-range (4-8 cores)**:
- Processing times as documented
- Standard settings work well

**High-end (8+ cores)**:
- Processing times 0.5-0.7x documented
- Can use higher FPS and resolution

### GPU Acceleration

With GPU (CUDA/Metal):
- Processing times: 0.3-0.5x CPU times
- Significantly faster for demographics
- Enable if available for production

### Browser Performance

**Desktop Browsers**:
- Full performance as documented
- WebSocket overhead minimal (~10-20ms)

**Mobile Browsers**:
- Processing times: 1.5-2x documented
- WebSocket overhead higher (~30-50ms)
- Battery drain consideration
- Use lower FPS and resolution

---

## Monitoring and Optimization

### Key Metrics to Track

1. **Average Processing Time** - Track per mode
2. **P95 Latency** - For consistent UX
3. **Frame Drop Rate** - If processing can't keep up
4. **Success Rate** - Percentage of successful analyses
5. **WebSocket Latency** - Network overhead

### Performance Alerts

Set up monitoring for:
- Processing time > 2x expected
- Frame drop rate > 10%
- Error rate > 5%
- WebSocket disconnections

### Optimization Checklist

- [ ] Use appropriate FPS per mode
- [ ] Implement frame skipping for slow modes
- [ ] Use optimal resolution (720p default)
- [ ] Enable GPU acceleration if available
- [ ] Optimize database queries (verification/search)
- [ ] Implement connection pooling
- [ ] Use CDN for static assets
- [ ] Monitor and log performance metrics
- [ ] Set up performance alerts
- [ ] Regular benchmark testing

---

## Testing Your Performance

### Quick Test (Without Server)

```bash
# Run simple benchmark
python scripts/benchmark_simple.py --frames 50
```

### Full Test (With Server Running)

```bash
# Start backend
docker-compose up -d

# Run comprehensive benchmark
python scripts/benchmark_live_analysis.py --frames 100

# With custom test image
python scripts/benchmark_live_analysis.py \
  --frames 100 \
  --image path/to/test/face.jpg
```

### Continuous Monitoring

```bash
# Run daily benchmarks
python scripts/benchmark_live_analysis.py \
  --frames 100 \
  --output "benchmark_$(date +%Y%m%d).json"
```

---

## Conclusion

The live analysis system provides a range of real-time biometric processing capabilities. By following these performance guidelines and recommendations:

1. **Fast modes** (face detection, landmarks) can run at 15-30 FPS for smooth real-time experience
2. **Moderate modes** (quality, liveness, verification) work well at 8-15 FPS for good interactive UX
3. **Slow modes** (demographics, search) should run at 2-5 FPS with frame skipping
4. **Full analysis** is best for batch processing at 1-2 FPS

Always test performance on your target hardware and adjust FPS settings accordingly. The provided benchmarking tools will help you determine optimal settings for your specific deployment environment.
