#!/usr/bin/env python3
"""Performance benchmark for live camera analysis features.

This script measures the processing time and maximum sustainable FPS
for each analysis mode to help determine optimal frame rates.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import statistics

import websockets
import cv2
import base64
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn


console = Console()


class PerformanceBenchmark:
    """Benchmark live analysis performance."""

    def __init__(self, ws_url: str = "ws://localhost:8000/ws/live-analysis"):
        self.ws_url = ws_url
        self.test_image_path = None
        self.results: Dict[str, List[float]] = {}

    def load_test_image(self, image_path: Optional[str] = None) -> np.ndarray:
        """Load a test image for benchmarking."""
        if image_path and Path(image_path).exists():
            img = cv2.imread(image_path)
            self.test_image_path = image_path
        else:
            # Create a synthetic test image if no image provided
            console.print("[yellow]No test image provided, creating synthetic image[/yellow]")
            img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            # Draw a simple face-like pattern
            cv2.circle(img, (320, 240), 100, (200, 200, 200), -1)  # Face
            cv2.circle(img, (280, 220), 20, (50, 50, 50), -1)  # Left eye
            cv2.circle(img, (360, 220), 20, (50, 50, 50), -1)  # Right eye
            cv2.ellipse(img, (320, 270), (40, 20), 0, 0, 180, (100, 100, 100), 2)  # Mouth

        console.print(f"[green]Loaded test image: {img.shape}[/green]")
        return img

    def encode_image(self, img: np.ndarray) -> str:
        """Encode image to base64 JPEG."""
        _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode('utf-8')

    async def benchmark_mode(
        self,
        mode: str,
        num_frames: int = 50,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, float]:
        """Benchmark a specific analysis mode."""
        console.print(f"\n[bold cyan]Benchmarking mode: {mode}[/bold cyan]")

        # Load test image
        img = self.load_test_image()
        img_base64 = self.encode_image(img)

        processing_times = []
        total_times = []
        successful_frames = 0
        errors = 0

        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Send configuration
                config = {
                    "type": "config",
                    "data": {
                        "mode": mode,
                        "frame_skip": 0,
                        "quality_threshold": 70.0,
                    }
                }
                if user_id:
                    config["data"]["user_id"] = user_id
                if tenant_id:
                    config["data"]["tenant_id"] = tenant_id

                await websocket.send(json.dumps(config))

                # Wait for config acknowledgment
                response = await websocket.recv()
                msg = json.loads(response)
                if msg.get("type") != "config_ack":
                    console.print(f"[red]Failed to configure mode {mode}: {msg}[/red]")
                    return {}

                console.print(f"[green]Mode configured successfully[/green]")

                # Send frames and measure performance
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"Processing {num_frames} frames...", total=num_frames)

                    for i in range(num_frames):
                        # Measure total time (including network)
                        start_total = time.perf_counter()

                        # Send frame
                        frame_msg = {
                            "type": "frame",
                            "data": img_base64,
                        }
                        await websocket.send(json.dumps(frame_msg))

                        # Receive result
                        response = await websocket.recv()
                        end_total = time.perf_counter()

                        msg = json.loads(response)

                        if msg.get("type") == "result":
                            data = msg.get("data", {})
                            if data.get("error"):
                                console.print(f"[yellow]Frame {i}: Error - {data['error']}[/yellow]")
                                errors += 1
                            else:
                                processing_time = data.get("processing_time_ms", 0)
                                processing_times.append(processing_time)
                                total_times.append((end_total - start_total) * 1000)
                                successful_frames += 1

                        progress.update(task, advance=1)

                        # Small delay to avoid overwhelming the server
                        await asyncio.sleep(0.01)

        except Exception as e:
            console.print(f"[red]Error during benchmark: {e}[/red]")
            return {}

        # Calculate statistics
        if processing_times:
            stats = {
                "mode": mode,
                "total_frames": num_frames,
                "successful_frames": successful_frames,
                "errors": errors,
                "avg_processing_ms": statistics.mean(processing_times),
                "min_processing_ms": min(processing_times),
                "max_processing_ms": max(processing_times),
                "median_processing_ms": statistics.median(processing_times),
                "stdev_processing_ms": statistics.stdev(processing_times) if len(processing_times) > 1 else 0,
                "avg_total_ms": statistics.mean(total_times),
                "max_sustainable_fps": 1000 / statistics.mean(processing_times),
                "p95_processing_ms": sorted(processing_times)[int(len(processing_times) * 0.95)],
                "p99_processing_ms": sorted(processing_times)[int(len(processing_times) * 0.99)],
            }

            self.results[mode] = processing_times
            return stats
        else:
            console.print(f"[red]No successful frames for mode {mode}[/red]")
            return {}

    async def run_all_benchmarks(self, num_frames: int = 50) -> List[Dict]:
        """Run benchmarks for all analysis modes."""
        modes = [
            ("face_detection", None, None),
            ("quality", None, None),
            ("demographics", None, None),
            ("liveness", None, None),
            ("enrollment_ready", None, None),
            # ("verification", "test_user", None),  # Requires enrolled user
            # ("search", None, None),  # Requires database with faces
            ("landmarks", None, None),
        ]

        all_stats = []

        for mode, user_id, tenant_id in modes:
            stats = await self.benchmark_mode(mode, num_frames, user_id, tenant_id)
            if stats:
                all_stats.append(stats)
            await asyncio.sleep(1)  # Pause between modes

        return all_stats

    def print_results(self, all_stats: List[Dict]):
        """Print benchmark results in a formatted table."""
        console.print("\n[bold green]Performance Benchmark Results[/bold green]\n")

        # Create main results table
        table = Table(title="Analysis Mode Performance", show_header=True, header_style="bold magenta")
        table.add_column("Mode", style="cyan", width=20)
        table.add_column("Avg (ms)", justify="right", style="green")
        table.add_column("Min (ms)", justify="right")
        table.add_column("Max (ms)", justify="right")
        table.add_column("P95 (ms)", justify="right")
        table.add_column("Max FPS", justify="right", style="bold yellow")
        table.add_column("Success Rate", justify="right")

        for stats in all_stats:
            success_rate = f"{(stats['successful_frames'] / stats['total_frames']) * 100:.1f}%"
            table.add_row(
                stats["mode"],
                f"{stats['avg_processing_ms']:.2f}",
                f"{stats['min_processing_ms']:.2f}",
                f"{stats['max_processing_ms']:.2f}",
                f"{stats['p95_processing_ms']:.2f}",
                f"{stats['max_sustainable_fps']:.1f}",
                success_rate,
            )

        console.print(table)

        # Print recommendations
        console.print("\n[bold blue]Recommendations:[/bold blue]")
        for stats in all_stats:
            mode = stats["mode"]
            max_fps = stats["max_sustainable_fps"]

            if max_fps >= 30:
                recommended_fps = "15-30 FPS (real-time video)"
                color = "green"
            elif max_fps >= 15:
                recommended_fps = "5-15 FPS (smooth interactive)"
                color = "yellow"
            elif max_fps >= 5:
                recommended_fps = "2-5 FPS (interactive)"
                color = "orange"
            else:
                recommended_fps = "1-2 FPS (slow processing)"
                color = "red"

            console.print(f"  [{color}]{mode:20s}[/{color}] → {recommended_fps}")

        # Print summary statistics
        console.print("\n[bold blue]Summary Statistics:[/bold blue]")
        if all_stats:
            avg_of_avgs = statistics.mean([s["avg_processing_ms"] for s in all_stats])
            fastest_mode = min(all_stats, key=lambda s: s["avg_processing_ms"])
            slowest_mode = max(all_stats, key=lambda s: s["avg_processing_ms"])

            console.print(f"  Average processing time across all modes: {avg_of_avgs:.2f} ms")
            console.print(f"  Fastest mode: [green]{fastest_mode['mode']}[/green] ({fastest_mode['avg_processing_ms']:.2f} ms)")
            console.print(f"  Slowest mode: [red]{slowest_mode['mode']}[/red] ({slowest_mode['avg_processing_ms']:.2f} ms)")

    def save_results(self, all_stats: List[Dict], output_file: str = "benchmark_results.json"):
        """Save benchmark results to JSON file."""
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "test_image": str(self.test_image_path) if self.test_image_path else "synthetic",
            "results": all_stats,
        }

        output_path = Path(__file__).parent.parent / output_file
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        console.print(f"\n[green]Results saved to: {output_path}[/green]")


async def main():
    """Main benchmark function."""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark live camera analysis performance")
    parser.add_argument(
        "--url",
        default="ws://localhost:8000/ws/live-analysis",
        help="WebSocket URL for live analysis",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=50,
        help="Number of frames to test per mode (default: 50)",
    )
    parser.add_argument(
        "--image",
        help="Path to test image (optional, will use synthetic image if not provided)",
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="Output file for results (default: benchmark_results.json)",
    )

    args = parser.parse_args()

    console.print("[bold blue]Live Camera Analysis Performance Benchmark[/bold blue]")
    console.print(f"WebSocket URL: {args.url}")
    console.print(f"Frames per mode: {args.frames}")
    console.print(f"Test image: {args.image or 'synthetic'}\n")

    benchmark = PerformanceBenchmark(ws_url=args.url)

    # Load custom image if provided
    if args.image:
        benchmark.load_test_image(args.image)

    # Run benchmarks
    all_stats = await benchmark.run_all_benchmarks(num_frames=args.frames)

    # Print and save results
    benchmark.print_results(all_stats)
    benchmark.save_results(all_stats, args.output)


if __name__ == "__main__":
    asyncio.run(main())
