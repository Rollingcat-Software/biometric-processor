# Server Providers Research: GPU & CPU VPS for Biometric Processor

> Research Date: February 2, 2026

## Table of Contents

- [Architecture Context](#architecture-context)
- [CPU VPS Providers (Identity Core API)](#cpu-vps-providers-identity-core-api)
- [GPU VPS Providers (Biometric Processor)](#gpu-vps-providers-biometric-processor)
- [Recommendation Summary](#recommendation-summary)

---

## Architecture Context

The system consists of two microservices:

```
[Identity Core API (VPS)]     →  Standard web API, database-heavy
       ↓ calls
[Biometric Processor (GPU)]   →  ML inference: face detection, embeddings,
                                  liveness detection, quality assessment
```

**Identity Core API** — runs on a standard CPU VPS. Handles authentication, user management, and orchestrates biometric operations by calling the Biometric Processor API.

**Biometric Processor** — the compute-heavy service. Runs DeepFace (TensorFlow), MediaPipe, YOLO models for:
- Face detection & embedding extraction (128–2622D vectors)
- Liveness detection (passive + active anti-spoofing)
- Quality assessment, demographics, 468-point landmarks
- Card/document type detection (YOLO)
- Real-time proctoring via WebSocket

### Current Resource Requirements

| Config | CPU | RAM | Notes |
|--------|-----|-----|-------|
| **Minimum (dev)** | 2 cores | 2 GB | Single-user, slow inference |
| **Production (CPU-only)** | 2–4 cores | 4 GB | 18–30 FPS, ~200–500ms/enrollment |
| **Production (GPU)** | 2 cores + 1 GPU | 4 GB + GPU VRAM | 50–80 FPS (est. 2.5–3x speedup) |
| **HA cluster (K8s)** | 3 nodes × 2 CPU | 3 × 2 GB | Auto-scales to 20 replicas |

---

## CPU VPS Providers (Identity Core API)

The Identity Core API is a standard REST API with PostgreSQL + Redis. A **2 vCPU / 4 GB RAM** VPS is sufficient.

### Pricing Comparison

| Provider | Plan | vCPU | RAM | Storage | Traffic | Price/mo |
|----------|------|------|-----|---------|---------|----------|
| **Hetzner** | CX22 | 2 (shared) | 4 GB | 40 GB NVMe | 20 TB | ~€3.79 (~$4–5) |
| **Contabo** | Cloud VPS 10 | 3–4 (shared) | 8 GB | 75–150 GB | Unlimited* | ~$3.96–$4.95 |
| **DigitalOcean** | Basic 2vCPU | 2 (shared) | 4 GB | 80 GB SSD | 4 TB | ~$24 |
| **DigitalOcean** | CPU-Optimized | 2 (dedicated) | 4 GB | 25 GB SSD | 4 TB | ~$42 |
| **Linode/Akamai** | Shared 4GB | 2 (shared) | 4 GB | 80 GB SSD | 4 TB | ~$24 |
| **Vultr** | Cloud Compute | 2 (shared) | 4 GB | 80 GB SSD | 3 TB | ~$24 |

*\*Contabo: fair-use policy, 200 Mbit/s–1 Gbit/s port*

### Assessment

| Provider | Price | Performance | UX / Docs | Best For |
|----------|-------|-------------|-----------|----------|
| **Hetzner** | Excellent | Excellent | Minimal | Experienced devs, best value |
| **Contabo** | Excellent | Moderate | Basic | Max specs per dollar |
| **DigitalOcean** | Moderate | Good | Excellent | Dev experience, tutorials |

**Recommendation for Identity Core API:** Hetzner CX22 (~$5/mo) or Contabo VPS 10 (~$4–5/mo). Both are sufficient for a REST API + PostgreSQL + Redis stack.

---

## GPU VPS Providers (Biometric Processor)

The biometric processor needs GPU acceleration for production-grade inference. Current CPU-only performance is 18–30 FPS; GPU is expected to deliver 50–80 FPS.

### What GPU Does the Biometric Processor Need?

The ML stack (TensorFlow 2.15 + DeepFace + MediaPipe + YOLO) requires:
- **Minimum VRAM:** 4–6 GB (fits all models concurrently)
- **Recommended VRAM:** 8–16 GB (comfortable headroom for batch processing)
- **CUDA:** 12.2+ with cuDNN 8
- **Best fit:** NVIDIA T4 (16 GB, inference-optimized) or RTX A4000/A6000

### GPU VPS Pricing Comparison

#### Budget Tier (< $1/hr) — Good for Dev/Staging & Light Production

| Provider | GPU | VRAM | Price/hr | Price/mo (24/7) | Notes |
|----------|-----|------|----------|-----------------|-------|
| **Vast.ai** | RTX 3090 | 24 GB | $0.11–0.31 | $80–225 | Marketplace, variable availability |
| **Vast.ai** | T4 | 16 GB | ~$0.15–0.30 | $108–216 | Community GPUs |
| **Thunder Compute** | T4 | 16 GB | $0.29 | $209 | Simple UX |
| **RunPod** | RTX 4090 | 24 GB | $0.34 | $245 | Community cloud |
| **Hyperstack** | RTX A6000 | 48 GB | $0.50 | $360 | Good value for VRAM |
| **TensorDock** | A100 40GB | 40 GB | $0.75 | $540 | KVM isolation |
| **Thunder Compute** | A100 | 80 GB | $0.66 | $475 | On-demand |

#### Mid Tier ($1–3/hr) — Production Workloads

| Provider | GPU | VRAM | Price/hr | Price/mo (24/7) | Notes |
|----------|-----|------|----------|-----------------|-------|
| **GCP** | T4 | 16 GB | $0.35–0.95 | $252–684 | Attached to N1 VMs |
| **GCP** | A100 40GB | 40 GB | ~$1.15 | $828 | Spot pricing |
| **Lambda Labs** | A100 40GB | 40 GB | $1.29 | $929 | Dedicated instances |
| **Northflank** | A100 40GB | 40 GB | $1.42 | $1,022 | Managed platform |
| **GCP** | A100 80GB | 80 GB | ~$1.57 | $1,130 | On-demand |
| **RunPod** | H100 PCIe | 80 GB | $1.99 | $1,433 | On-demand |
| **TensorDock** | H100 SXM5 | 80 GB | $2.25 | $1,620 | No quotas |

#### Enterprise / Hyperscaler Tier

| Provider | GPU | VRAM | Price/hr | Notes |
|----------|-----|------|----------|-------|
| **AWS** | T4 (g4dn) | 16 GB | ~$0.53 | Ecosystem, compliance |
| **AWS** | A100 (p4d) | 40 GB | ~$4.10/GPU | 8-GPU minimum |
| **Azure** | T4 (spot) | 16 GB | ~$0.09 | Spot only, can be interrupted |
| **GCP** | L4 | 24 GB | ~$0.70 | New inference-optimized |

### Serverless GPU Options (Pay-per-inference)

For variable load, serverless GPU can be cost-effective:

| Provider | GPU | Price Model | Notes |
|----------|-----|-------------|-------|
| **RunPod Serverless** | A100 80GB | $0.0008–0.0011/sec (~$2.88–3.96/hr active) | Pay only when running |
| **Modal** | T4/A100 | Per-second billing | Cold starts ~2–5s |
| **GCP Cloud Run + GPU** | L4/T4 | Per-request + GPU-seconds | Currently in preview |

---

## Recommendation Summary

### For Identity Core API (CPU VPS)

| Scenario | Provider | Spec | Cost/mo |
|----------|----------|------|---------|
| **Budget / Dev** | Hetzner CX22 | 2 vCPU, 4 GB, 40 GB NVMe | ~$5 |
| **Budget + More RAM** | Contabo VPS 10 | 3–4 vCPU, 8 GB, 150 GB | ~$4–5 |
| **Production (DX)** | DigitalOcean | 2 vCPU, 4 GB, 80 GB | ~$24 |

### For Biometric Processor (GPU)

| Scenario | Provider | GPU | Cost/mo | Justification |
|----------|----------|-----|---------|---------------|
| **Dev/Testing** | Vast.ai | RTX 3090 | ~$80–150 | Cheapest, good for dev |
| **Staging** | Thunder Compute | T4 | ~$209 | Stable, simple |
| **Production (Budget)** | RunPod Community | RTX 4090 | ~$245 | Good perf/price |
| **Production (Reliable)** | TensorDock | A100 40GB | ~$540 | KVM isolation, reliable |
| **Production (Variable Load)** | RunPod Serverless | A100 | Pay-per-use | Best for bursty traffic |
| **Production (Compliance)** | GCP Cloud Run | T4/L4 | ~$252–684 | HIPAA/SOC2, current setup |
| **Production (Scale)** | Lambda Labs | A100 | ~$929 | Dedicated, consistent |

### Architecture Decision: CPU-Only vs GPU

The biometric processor **currently runs on CPU-only** (TensorFlow-CPU 2.15.0). For many use cases, this may be sufficient:

| Metric | CPU-Only (2 cores) | GPU (T4) | GPU (A100) |
|--------|-------------------|----------|------------|
| Enrollment latency | 200–500ms | ~80–200ms | ~50–100ms |
| Throughput (FPS) | 18–30 | 50–80 | 100–150 |
| Cost/mo (24/7) | $5–24 | $108–540 | $475–929 |
| Best for | < 50 users/min | 50–500 users/min | 500+ users/min |

**If your load is < 50 concurrent enrollments/minute, a CPU VPS ($5–24/mo) may be all you need.** GPU becomes valuable when you need real-time video processing (proctoring), batch operations, or high-throughput 1:N search.

### Combined Stack Cost Estimates

| Tier | Identity Core | Biometric Proc. | PostgreSQL | Redis | Total/mo |
|------|--------------|-----------------|------------|-------|----------|
| **Dev** | Hetzner $5 | CPU-only (same box) | Embedded | Embedded | **~$5** |
| **Staging** | Hetzner $5 | Vast.ai RTX 3090 $100 | Managed $15 | Managed $10 | **~$130** |
| **Prod (CPU)** | DO $24 | Hetzner $10 (4 CPU) | DO Managed $15 | DO Managed $15 | **~$64** |
| **Prod (GPU)** | DO $24 | RunPod 4090 $245 | DO Managed $15 | DO Managed $15 | **~$300** |
| **Prod (Scale)** | K8s cluster | TensorDock A100 $540 | CloudSQL $50 | Redis Cloud $30 | **~$700** |

---

## Sources

- [GPU Price Comparison 2026 — GetDeploying](https://getdeploying.com/gpus)
- [7 Cheapest Cloud GPU Providers 2026 — Northflank](https://northflank.com/blog/cheapest-cloud-gpu-providers)
- [Top 12 Cloud GPU Providers — RunPod](https://www.runpod.io/articles/guides/top-cloud-gpu-providers)
- [5 Best Cloud GPU Providers — Hyperstack](https://www.hyperstack.cloud/blog/case-study/best-cloud-gpu-providers-for-ai)
- [DigitalOcean GPU Droplets](https://www.digitalocean.com/resources/articles/cloud-gpu-provider)
- [HOSTKEY GPU VPS](https://hostkey.com/dedicated-servers/gpu-vps/)
- [Vast.ai GPU Marketplace](https://vast.ai/)
- [Lambda AI Pricing](https://lambda.ai/pricing)
- [RunPod Pricing](https://www.runpod.io/pricing)
- [Hetzner Cloud VPS](https://www.hetzner.com/cloud)
- [Contabo VPS](https://contabo.com/en-us/vps/)
- [DigitalOcean Droplet Pricing](https://www.digitalocean.com/pricing/droplets)
- [Top 10 Low-Cost VPS Providers 2026 — Nucamp](https://www.nucamp.co/blog/top-10-low-cost-vps-providers-in-2026-affordable-alternatives-to-aws-azure-gcp-and-vercel)
- [NVIDIA A100 Cloud Options — Fluence](https://www.fluence.network/blog/nvidia-a100/)
- [Thunder Compute Pricing](https://www.thundercompute.com/blog/cheapest-cloud-gpu-providers-in-2025)
