"""Head angles from MediaPipe's facial transformation matrix.

We only need how far the head turned away from the student's own normal
position, so we take the face's forward direction and convert it to a
horizontal angle (yaw) and a vertical angle (pitch). The sign convention
(left vs right) should be checked once with a real webcam; the indicators
only use the size of the deviation, so the sign does not affect them.
"""
import math

import numpy as np


def yaw_pitch_from_matrix(matrix) -> tuple:
    m = np.asarray(matrix, dtype=float)
    r = m[:3, :3]
    # remove any scale in the matrix so r is a pure rotation
    r = r / np.linalg.norm(r, axis=0, keepdims=True)
    forward = r @ np.array([0.0, 0.0, 1.0])
    fx, fy, fz = forward
    yaw = math.degrees(math.atan2(fx, fz))
    pitch = math.degrees(math.atan2(-fy, math.hypot(fx, fz)))
    return yaw, pitch


def angular_deviation(yaw, pitch, base_yaw, base_pitch) -> float:
    """Size of the head turn relative to baseline, in degrees."""
    dy = (yaw - base_yaw + 180.0) % 360.0 - 180.0
    dp = pitch - base_pitch
    return math.hypot(dy, dp)
