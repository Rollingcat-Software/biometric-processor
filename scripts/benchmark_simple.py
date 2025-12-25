#!/usr/bin/env python3
"""Simple performance benchmark for analysis modes (direct testing without WebSocket).

This script directly calls the use case methods to benchmark pure processing time
without WebSocket/network overhead.
"""

import asyncio
import time
from pathlib import Path
import statistics
from typing import Dict, List
import sys

import numpy as np
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.ml.mediapipe_detector import MediaPipeFaceDetector
from app.infrastructure.ml.mediapipe_quality import MediaPipeQualityAssessor
from app.application.use_cases.live_camera_analysis import LiveCameraAnalysisUseCase
from app.api.schemas.live_analysis import AnalysisMode


console = Console()


class SimplePerformanceBenchmark:
    """Direct performance benchmark without network overhead."""

    def __init__(self):
        self.detector = None
        self.quality_assessor = None
        self.use_case = None
        self.results: Dict[str, List[float]] = {}

    def setup(self):
        """Initialize components."""
        console.print("[cyan]Initializing ML components...[/cyan]")

        try:
            self.detector = MediaPipeFaceDetector()
            self.quality_assessor = MediaPipeQualityAssessor()
            self.use_case = LiveCameraAnalysisUseCase(
                detector=self.detector,
                quality_assessor=self.quality_assessor,
            )
            console.print("[green]✓ Components initialized[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to initialize: {e}[/red]")
            raise

    def generate_test_image(self, size=(640, 480)) -> np.ndarray:
        """Generate a synthetic test image."""
        img = np.random.randint(0, 255, (*size, 3), dtype=np.uint8)
        # Draw simple face-like pattern
        center_x, center_y = size[0] // 2, size[1] // 2

        # Face circle
        for y in range(size[1]):
            for x in range(size[0]):
                dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                if dist < 100:
                    img[y, x] = [200, 200, 200]

        # Eyes
        for y in range(size[1]):
            for x in range(size[0]):
                left_eye_dist = np.sqrt((x - (center_x - 40))**2 + (y - (center_y - 20))**2)
                right_eye_dist = np.sqrt((x - (center_x + 40))**2 + (y - (center_y - 20))**2)
                if left_eye_dist < 15 or right_eye_dist < 15:
                    img[y, x] = [50, 50, 50]

        return img

    async def benchmark_mode(self, mode: AnalysisMode, num_frames: int = 50) -> Dict:
        """Benchmark a specific mode."""
        console.print(f"\n[bold cyan]Benchmarking: {mode.value}[/bold cyan]")

        img = self.generate_test_image()
        processing_times = []
        successful = 0
        errors = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Processing {num_frames} frames...", total=num_frames)

            for _ in range(num_frames):
                try:
                    start = time.perf_counter()

                    result = await self.use_case.analyze_frame(
                        image=img,
                        mode=mode,
                        quality_threshold=70.0,
                    )

                    end = time.perf_counter()
                    elapsed_ms = (end - start) * 1000

                    if not result.error:
                        processing_times.append(elapsed_ms)
                        successful += 1
                    else:
                        errors += 1

                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    errors += 1

                progress.update(task, advance=1)

        if processing_times:
            return {
                "mode": mode.value,
                "total_frames": num_frames,
                "successful": successful,
                "errors": errors,
                "avg_ms": statistics.mean(processing_times),
                "min_ms": min(processing_times),
                "max_ms": max(processing_times),
                "median_ms": statistics.median(processing_times),
                "stdev_ms": statistics.stdev(processing_times) if len(processing_times) > 1 else 0,
                "p95_ms": sorted(processing_times)[int(len(processing_times) * 0.95)],
                "p99_ms": sorted(processing_times)[int(len(processing_times) * 0.99)],
                "max_fps": 1000 / statistics.mean(processing_times),
            }
        return {}

    async def run_benchmarks(self, num_frames: int = 50) -> List[Dict]:
        """Run all benchmarks."""
        modes = [
            AnalysisMode.FACE_DETECTION,
            AnalysisMode.QUALITY_ONLY,
            AnalysisMode.ENROLLMENT_READY,
            # Add others as needed
        ]

        results = []
        for mode in modes:
            stats = await self.benchmark_mode(mode, num_frames)
            if stats:
                results.append(stats)

        return results

    def print_results(self, results: List[Dict]):
        """Print formatted results."""
        console.print("\n[bold green]Simple Benchmark Results (Direct Processing)[/bold green]\n")

        table = Table(title="Processing Performance", show_header=True, header_style="bold magenta")
        table.add_column("Mode", style="cyan", width=20)
        table.add_column("Avg (ms)", justify="right", style="green")
        table.add_column("Min (ms)", justify="right")
        table.add_column("Max (ms)", justify="right")
        table.add_column("P95 (ms)", justify="right")
        table.add_column("Max FPS", justify="right", style="bold yellow")
        table.add_column("Success", justify="right")

        for stats in results:
            success_rate = f"{(stats['successful'] / stats['total_frames']) * 100:.1f}%"
            table.add_row(
                stats["mode"],
                f"{stats['avg_ms']:.2f}",
                f"{stats['min_ms']:.2f}",
                f"{stats['max_ms']:.2f}",
                f"{stats['p95_ms']:.2f}",
                f"{stats['max_fps']:.1f}",
                success_rate,
            )

        console.print(table)

        # Print recommendations
        console.print("\n[bold blue]Recommended FPS Settings:[/bold blue]")
        for stats in results:
            max_fps = stats["max_fps"]
            mode = stats["mode"]

            # Account for ~30-50ms WebSocket overhead
            websocket_overhead = 40  # ms
            effective_fps = 1000 / (stats["avg_ms"] + websocket_overhead)

            if effective_fps >= 20:
                rec = f"10-15 FPS (with WebSocket: ~{effective_fps:.1f} max)"
                color = "green"
            elif effective_fps >= 10:
                rec = f"5-10 FPS (with WebSocket: ~{effective_fps:.1f} max)"
                color = "yellow"
            elif effective_fps >= 5:
                rec = f"2-5 FPS (with WebSocket: ~{effective_fps:.1f} max)"
                color = "orange"
            else:
                rec = f"1-2 FPS (with WebSocket: ~{effective_fps:.1f} max)"
                color = "red"

            console.print(f"  [{color}]{mode:20s}[/{color}] → {rec}")

        console.print("\n[dim]Note: These are pure processing times. Add ~30-50ms for WebSocket overhead in production.[/dim]")


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Simple performance benchmark (direct processing)")
    parser.add_argument("--frames", type=int, default=50, help="Number of frames per mode")
    args = parser.parse_args()

    console.print("[bold blue]Simple Performance Benchmark[/bold blue]")
    console.print("[dim]This measures pure processing time without network overhead[/dim]\n")

    benchmark = SimplePerformanceBenchmark()

    try:
        benchmark.setup()
        results = await benchmark.run_benchmarks(num_frames=args.frames)
        benchmark.print_results(results)
    except Exception as e:
        console.print(f"[red]Benchmark failed: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
