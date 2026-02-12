
import time
from collections import deque

class PerformanceMonitor:
    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.times = {
            'inference': deque(maxlen=window_size),
            'render_2d': deque(maxlen=window_size),
            'render_3d': deque(maxlen=window_size),
            'total': deque(maxlen=window_size)
        }
        self.global_stats = {
            'inference': {'sum': 0.0, 'count': 0},
            'render_2d': {'sum': 0.0, 'count': 0},
            'render_3d': {'sum': 0.0, 'count': 0},
            'total': {'sum': 0.0, 'count': 0}
        }
        self.start_times = {}

    def start(self, name: str):
        """Start a timer for a specific block."""
        self.start_times[name] = time.perf_counter()

    def stop(self, name: str):
        """Stop a timer and record the duration (ms)."""
        if name in self.start_times:
            duration = (time.perf_counter() - self.start_times[name]) * 1000
            self.times[name].append(duration)
            
            # Update global stats
            if name in self.global_stats:
                self.global_stats[name]['sum'] += duration
                self.global_stats[name]['count'] += 1
                
            del self.start_times[name]

    def get_avg(self, name: str) -> float:
        """Get moving average duration (ms) for a block."""
        if name in self.times and self.times[name]:
            return sum(self.times[name]) / len(self.times[name])
        return 0.0

    def get_fps(self) -> float:
        """Calculate FPS based on 'total' loop time."""
        avg_total = self.get_avg('total')
        return 1000.0 / avg_total if avg_total > 0 else 0.0

    def get_global_avg(self, name: str) -> float:
        if name in self.global_stats:
            s = self.global_stats[name]
            return s['sum'] / s['count'] if s['count'] > 0 else 0.0
        return 0.0

    def report(self) -> str:
        """Return a formatted string report."""
        fps = self.get_fps()
        inf = self.get_avg('inference')
        r2d = self.get_avg('render_2d')
        r3d = self.get_avg('render_3d')
        return f"FPS: {fps:.1f} | Inf: {inf:.1f}ms | 2D: {r2d:.1f}ms | 3D: {r3d:.1f}ms"

    def final_report(self):
        """Print a summary of the entire session."""
        total_frames = self.global_stats['total']['count']
        if total_frames == 0:
            return "No frames processed."

        avg_total = self.global_avg('total')
        avg_inf = self.global_avg('inference')
        avg_2d = self.global_avg('render_2d')
        avg_3d = self.global_avg('render_3d')

        fps = 1000.0 / avg_total if avg_total > 0 else 0.0
        
        report = (
            f"\n📊 --- PERFORMANCE BENCHMARK ---\n"
            f"Frames Processed: {total_frames}\n"
            f"Average FPS:      {fps:.2f}\n"
            f"Inference Time:   {avg_inf:.2f} ms\n"
            f"Render 2D Time:   {avg_2d:.2f} ms\n"
            f"Render 3D Time:   {avg_3d:.2f} ms\n"
            f"Total Loop Time:  {avg_total:.2f} ms\n"
            f"---------------------------------"
        )
        return report

    def global_avg(self, name):
        if self.global_stats[name]['count'] > 0:
            return self.global_stats[name]['sum'] / self.global_stats[name]['count']
        return 0.0
