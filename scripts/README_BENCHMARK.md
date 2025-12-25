# Live Analysis Performance Benchmark

This directory contains a performance benchmark tool to measure the processing speed and determine the maximum sustainable frame rate for each live analysis mode.

## Prerequisites

1. **Backend Server Running**: Ensure the backend server is running on `http://localhost:8000`

```bash
# From the project root
docker-compose up -d
# OR if running locally
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

2. **Required Python Packages**:
```bash
pip install websockets rich opencv-python
```

## Usage

### Basic Usage

Run the benchmark with default settings (50 frames per mode):

```bash
python scripts/benchmark_live_analysis.py
```

### Advanced Usage

```bash
# Custom number of frames
python scripts/benchmark_live_analysis.py --frames 100

# Custom WebSocket URL
python scripts/benchmark_live_analysis.py --url ws://localhost:8000/ws/live-analysis

# Use a specific test image
python scripts/benchmark_live_analysis.py --image path/to/test/face.jpg

# Custom output file
python scripts/benchmark_live_analysis.py --output my_benchmark.json
```

### Full Example

```bash
python scripts/benchmark_live_analysis.py \
  --frames 100 \
  --image tests/fixtures/sample_face.jpg \
  --output benchmark_$(date +%Y%m%d_%H%M%S).json
```

## Output

The benchmark will:

1. **Display real-time progress** for each analysis mode
2. **Print a formatted table** with performance metrics:
   - Average processing time (ms)
   - Min/Max processing time (ms)
   - P95/P99 latency (ms)
   - Maximum sustainable FPS
   - Success rate

3. **Show recommendations** for each mode based on performance
4. **Save detailed results** to a JSON file for further analysis

### Sample Output

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Mode               ┃ Avg (ms) ┃ Min (ms) ┃ Max (ms) ┃ P95 (ms) ┃ Max FPS  ┃ Success Rate ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ face_detection     │    15.23 │    12.45 │    45.67 │    18.90 │     65.7 │       100.0% │
│ quality            │    45.67 │    38.90 │    89.12 │    67.34 │      21.9 │       100.0% │
│ demographics       │   234.56 │   198.34 │   456.78 │   345.67 │       4.3 │        98.0% │
│ liveness           │   123.45 │    98.76 │   234.56 │   189.01 │       8.1 │        96.0% │
│ enrollment_ready   │    67.89 │    54.32 │   123.45 │    98.76 │      14.7 │       100.0% │
│ landmarks          │    34.56 │    28.90 │    78.90 │    56.78 │      28.9 │       100.0% │
└────────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘

Recommendations:
  face_detection       → 15-30 FPS (real-time video)
  quality              → 5-15 FPS (smooth interactive)
  demographics         → 2-5 FPS (interactive)
  liveness             → 5-15 FPS (smooth interactive)
  enrollment_ready     → 5-15 FPS (smooth interactive)
  landmarks            → 15-30 FPS (real-time video)
```

## Understanding the Results

### Performance Metrics

- **Avg (ms)**: Average processing time per frame
- **Min/Max (ms)**: Range of processing times
- **P95 (ms)**: 95th percentile latency (95% of frames process faster than this)
- **Max FPS**: Theoretical maximum frames per second (1000 / avg_ms)
- **Success Rate**: Percentage of frames processed without errors

### FPS Recommendations

Based on the results, the benchmark provides recommendations:

- **30+ FPS**: Real-time video quality, suitable for smooth live streaming
- **15-30 FPS**: Smooth interactive experience
- **5-15 FPS**: Good interactive experience with slight delay
- **2-5 FPS**: Adequate for interactive use cases
- **<2 FPS**: Limited to slow/batch processing

### Typical Performance Expectations

For reference, here are approximate performance ranges on modern hardware:

| Mode | Expected Avg (ms) | Expected Max FPS | Use Case |
|------|-------------------|------------------|----------|
| Face Detection | 10-30 | 30-100 | Very fast, suitable for real-time |
| Quality | 30-60 | 15-30 | Fast, good for live feedback |
| Demographics | 150-300 | 3-7 | Slower, use 2-5 FPS |
| Liveness | 80-150 | 7-12 | Moderate, use 5-10 FPS |
| Enrollment Ready | 50-100 | 10-20 | Fast, good for live guidance |
| Landmarks | 20-50 | 20-50 | Fast, suitable for real-time |
| Verification | 40-80 | 12-25 | Fast with database |
| Search | 100-500+ | 2-10 | Depends on database size |

**Note**: Actual performance depends on:
- Hardware (CPU/GPU)
- Image resolution
- Database size (for verification/search)
- ML model complexity
- Network latency (WebSocket overhead)

## Optimizing Performance

If your results are slower than expected:

1. **Reduce image resolution** in the frontend (640x480 vs 1920x1080)
2. **Use frame skipping** (`frame_skip: 1` or higher)
3. **Enable GPU acceleration** if available
4. **Optimize database** for verification/search modes
5. **Reduce JPEG quality** for faster encoding (trade-off: slight quality loss)
6. **Use dedicated hardware** (GPU inference, hardware encoders)

## Troubleshooting

### "Connection refused" error
- Ensure the backend server is running
- Check the WebSocket URL (default: `ws://localhost:8000/ws/live-analysis`)

### "No module named..." errors
- Install required packages: `pip install websockets rich opencv-python`

### Low FPS results
- Check if the server is running on adequate hardware
- Verify ML models are loaded correctly
- Check server logs for errors or warnings

### High variance in processing times
- This is normal - first frames may be slower (model loading)
- Database lookups can vary (verification/search modes)
- Consider running with more frames (--frames 100) for stable averages

## Integration with Frontend

Based on the benchmark results, update the FPS selector in your frontend live streaming components:

```typescript
// In LiveCameraStream component
const defaultFPS = {
  quality: 10,           // Adjust based on benchmark
  demographics: 3,       // Slower mode, lower FPS
  liveness: 5,
  enrollment_ready: 10,
  verification: 8,
  search: 3,             // Depends on DB size
  landmarks: 15,
};
```

## Continuous Monitoring

For production deployments:

1. Run benchmarks regularly to monitor performance degradation
2. Compare results over time to identify trends
3. Set up alerts if processing times exceed thresholds
4. Use the P95/P99 metrics for SLA definitions

## Next Steps

After reviewing the benchmark results:

1. Adjust the default FPS settings in the frontend components
2. Add frame skip options for slower modes
3. Consider implementing adaptive FPS based on processing time
4. Set up performance monitoring in production
