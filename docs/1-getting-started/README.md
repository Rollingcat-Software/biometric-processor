# Getting Started

Quick guides to get you up and running with the biometric processor!

## Documents

- **[DEMO_USAGE.md](DEMO_USAGE.md)** - Complete guide to using demo_local.py (recommended!)
- **[QUICK_START.md](QUICK_START.md)** - Quick start guide
- **[QUICK_TEST_GUIDE.md](QUICK_TEST_GUIDE.md)** - Quick testing guide

## Recommended Path

1. **Start with demo_local.py** - The best way to test the system
   ```bash
   python demo_local.py
   ```
   See [DEMO_USAGE.md](DEMO_USAGE.md) for full documentation.

2. **Read the API Reference** - Understand the REST API
   See [../2-api-documentation/API_REFERENCE.md](../2-api-documentation/API_REFERENCE.md)

3. **Deploy (if needed)** - Deploy to production
   See [../3-deployment/](../3-deployment/)

## Quick Command Reference

```bash
# Run demo with all features
python demo_local.py

# Run specific mode
python demo_local.py --mode landmarks
python demo_local.py --mode enroll
python demo_local.py --mode demographics

# Use different camera
python demo_local.py --camera 1
```

## Performance

**demo_local.py performance**: 18-30 FPS (CPU), optimized and production-ready!

See [../5-performance/DEMO_LOCAL_PERFORMANCE_ANALYSIS.md](../5-performance/DEMO_LOCAL_PERFORMANCE_ANALYSIS.md) for detailed analysis.
