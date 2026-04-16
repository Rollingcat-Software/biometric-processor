# Comprehensive API Test Report

**Generated:** 2025-12-28 17:24:44
**Duration:** 0.15 seconds
**Base URL:** https://biometric-api-902542798396.europe-west1.run.app/api/v1

---

## Executive Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| **Total Tests** | 35 | 100% |
| **✓ Passed** | 0 | 0.0% |
| **✗ Failed** | 35 | 100.0% |
| **⚠ Warnings** | 0 | 0.0% |
| **○ Skipped** | 0 | 0.0% |

### Overall Status
**✗ 35 TESTS FAILED** - Immediate attention required!

---

## Test Results by Endpoint

### ✗ `/compare` (0/3 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Compare: Same person (afuat vs afuat) | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Compare: Different persons (afuat vs aga) | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Compare: Same person (ahab vs ahab) | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/demographics/analyze` (0/4 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Demographics: Large image | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Demographics: Small image <224px | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Demographics: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Demographics: Different person | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/enroll` (0/5 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Enroll: User afuat | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Enroll: Duplicate afuat | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Enroll: User aga | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Enroll: User ahab | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Enroll: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/face/detect` (0/3 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Face Detect: Good image | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Face Detect: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Face Detect: Another person | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/faces/detect-all` (0/2 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Multi-Face: Single face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Multi-Face: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/health` (0/1 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Health Check | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/landmarks/detect` (0/3 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Landmarks: Good image | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Landmarks: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Landmarks: Different person | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/liveness/check` (0/3 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Liveness: Good image | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Liveness: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Liveness: Different person | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/quality/analyze` (0/4 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Quality: Large good image | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Quality: Small image | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Quality: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Quality: Different person | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/search` (0/3 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Search: Find afuat | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Search: Find aga | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Search: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

### ✗ `/verify` (0/4 passed)

| Test Name | Status | Details | Status Code | Response Time |
|-----------|--------|---------|-------------|---------------|
| Verify: Same person (afuat) | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Verify: Same person (aga) | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Verify: Wrong person | ✗ FAIL | 403 Forbidden | 0 | 0.000s |
| Verify: No face | ✗ FAIL | 403 Forbidden | 0 | 0.000s |

---

## Failed Tests Detail

### ✗ Health Check
- **Endpoint:** `/health`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Quality: Large good image
- **Endpoint:** `/quality/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Quality: Small image
- **Endpoint:** `/quality/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Quality: No face
- **Endpoint:** `/quality/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Quality: Different person
- **Endpoint:** `/quality/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Demographics: Large image
- **Endpoint:** `/demographics/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Demographics: Small image <224px
- **Endpoint:** `/demographics/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Demographics: No face
- **Endpoint:** `/demographics/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Demographics: Different person
- **Endpoint:** `/demographics/analyze`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Face Detect: Good image
- **Endpoint:** `/face/detect`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Face Detect: No face
- **Endpoint:** `/face/detect`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Face Detect: Another person
- **Endpoint:** `/face/detect`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Multi-Face: Single face
- **Endpoint:** `/faces/detect-all`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Multi-Face: No face
- **Endpoint:** `/faces/detect-all`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Landmarks: Good image
- **Endpoint:** `/landmarks/detect`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Landmarks: No face
- **Endpoint:** `/landmarks/detect`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Landmarks: Different person
- **Endpoint:** `/landmarks/detect`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Liveness: Good image
- **Endpoint:** `/liveness/check`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Liveness: No face
- **Endpoint:** `/liveness/check`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Liveness: Different person
- **Endpoint:** `/liveness/check`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Enroll: User afuat
- **Endpoint:** `/enroll`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Enroll: Duplicate afuat
- **Endpoint:** `/enroll`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Enroll: User aga
- **Endpoint:** `/enroll`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Enroll: User ahab
- **Endpoint:** `/enroll`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Enroll: No face
- **Endpoint:** `/enroll`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Verify: Same person (afuat)
- **Endpoint:** `/verify`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Verify: Same person (aga)
- **Endpoint:** `/verify`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Verify: Wrong person
- **Endpoint:** `/verify`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Verify: No face
- **Endpoint:** `/verify`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Search: Find afuat
- **Endpoint:** `/search`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Search: Find aga
- **Endpoint:** `/search`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Search: No face
- **Endpoint:** `/search`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Compare: Same person (afuat vs afuat)
- **Endpoint:** `/compare`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Compare: Different persons (afuat vs aga)
- **Endpoint:** `/compare`
- **Status Code:** 0
- **Details:** 403 Forbidden

### ✗ Compare: Same person (ahab vs ahab)
- **Endpoint:** `/compare`
- **Status Code:** 0
- **Details:** 403 Forbidden

---

## Performance Metrics

| Endpoint | Avg Response Time | Min | Max |
|----------|------------------|-----|-----|

---

## Recommendations

### Critical Issues
- **35 endpoints are failing** - Review the 'Failed Tests Detail' section above
- Fix these issues before deploying to production

---

*Report generated by Comprehensive API Tester*
