from __future__ import annotations

import math
import random
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class GestureConfig:
    enabled: bool = True
    tap_path_probability: float = 0.1
    pre_action_delay_mean: float = 0.0
    pre_action_delay_std: float = 0.0
    post_action_delay_mean: float = 0.0
    post_action_delay_std: float = 0.0
    swipe_duration_mean_ms: float = 520.0
    swipe_duration_std_ms: float = 140.0
    min_delay: float = 0.0
    max_delay: float = 1.0
    min_swipe_duration_ms: int = 180
    max_swipe_duration_ms: int = 1200
    curve_segments: int = 6


DEFAULT_GESTURE_CONFIG = GestureConfig()


class GestureController:
    def __init__(self, config: GestureConfig = DEFAULT_GESTURE_CONFIG):
        self.config = config

    def tap(self, x: int, y: int, device_id: str | None = None, delay: float | None = None) -> None:
        self._sleep_normal(self.config.pre_action_delay_mean, self.config.pre_action_delay_std)
        if self.config.enabled and random.random() < self.config.tap_path_probability:
            start_x, start_y = self._nearby_start(x, y)
            self.curve_swipe(start_x, start_y, x, y, device_id=device_id, duration_ms=self._duration_ms() // 2)
        self._adb(device_id, ["shell", "input", "tap", str(x), str(y)])
        if delay is not None:
            time.sleep(delay)
        else:
            self._sleep_normal(self.config.post_action_delay_mean, self.config.post_action_delay_std)

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int | None = None,
        device_id: str | None = None,
        delay: float | None = None,
    ) -> None:
        self._sleep_normal(self.config.pre_action_delay_mean, self.config.pre_action_delay_std)
        self.curve_swipe(
            start_x,
            start_y,
            end_x,
            end_y,
            device_id=device_id,
            duration_ms=duration_ms or self._duration_ms(),
        )
        if delay is not None:
            time.sleep(delay)
        else:
            self._sleep_normal(self.config.post_action_delay_mean, self.config.post_action_delay_std)

    def curve_swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        *,
        device_id: str | None = None,
        duration_ms: int,
    ) -> None:
        points = self._bezier_points(start_x, start_y, end_x, end_y)
        segment_duration = max(30, int(duration_ms / max(1, len(points) - 1)))
        for current, nxt in zip(points, points[1:]):
            self._adb(
                device_id,
                [
                    "shell",
                    "input",
                    "swipe",
                    str(current[0]),
                    str(current[1]),
                    str(nxt[0]),
                    str(nxt[1]),
                    str(segment_duration),
                ],
            )

    def _bezier_points(self, start_x: int, start_y: int, end_x: int, end_y: int) -> list[tuple[int, int]]:
        dx = end_x - start_x
        dy = end_y - start_y
        distance = max(1.0, math.hypot(dx, dy))
        normal_x = -dy / distance
        normal_y = dx / distance
        bend = min(120.0, max(20.0, distance * 0.15))
        c1 = (start_x + dx * 0.35 + normal_x * bend, start_y + dy * 0.35 + normal_y * bend)
        c2 = (start_x + dx * 0.70 - normal_x * bend * 0.6, start_y + dy * 0.70 - normal_y * bend * 0.6)

        points: list[tuple[int, int]] = []
        for index in range(self.config.curve_segments + 1):
            t = index / self.config.curve_segments
            x = (
                (1 - t) ** 3 * start_x
                + 3 * (1 - t) ** 2 * t * c1[0]
                + 3 * (1 - t) * t**2 * c2[0]
                + t**3 * end_x
            )
            y = (
                (1 - t) ** 3 * start_y
                + 3 * (1 - t) ** 2 * t * c1[1]
                + 3 * (1 - t) * t**2 * c2[1]
                + t**3 * end_y
            )
            points.append((max(0, round(x)), max(0, round(y))))
        return points

    def _nearby_start(self, x: int, y: int) -> tuple[int, int]:
        angle = random.uniform(0, math.tau)
        radius = random.uniform(24, 90)
        return max(0, round(x + math.cos(angle) * radius)), max(0, round(y + math.sin(angle) * radius))

    def _duration_ms(self) -> int:
        value = random.gauss(self.config.swipe_duration_mean_ms, self.config.swipe_duration_std_ms)
        return max(self.config.min_swipe_duration_ms, min(self.config.max_swipe_duration_ms, round(value)))

    def _sleep_normal(self, mean: float, std: float) -> None:
        value = random.gauss(mean, std)
        time.sleep(max(self.config.min_delay, min(self.config.max_delay, value)))

    @staticmethod
    def _adb(device_id: str | None, args: list[str]) -> None:
        command = ["adb"]
        if device_id:
            command += ["-s", device_id]
        subprocess.run(command + args, capture_output=True)


def install_phone_agent_gesture_patch(config: GestureConfig = DEFAULT_GESTURE_CONFIG) -> None:
    controller = GestureController(config)
    try:
        import phone_agent.adb as adb_module
        import phone_agent.adb.device as device_module
    except ImportError:
        return

    device_module.tap = controller.tap
    device_module.swipe = controller.swipe
    adb_module.tap = controller.tap
    adb_module.swipe = controller.swipe
