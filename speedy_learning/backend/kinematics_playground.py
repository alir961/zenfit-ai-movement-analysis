from __future__ import annotations

# Placeholder sandbox for future FK/IK experiments.
# Intentionally not imported by runtime server routes.

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

Vec3 = np.ndarray
Mat3 = np.ndarray
Mat4 = np.ndarray


@dataclass
class Joint:
    name: str
    parent: str
    child: str
    axis: Vec3
    q_index: Tuple[int, int]
    T_parent_to_joint: Mat4
    T_joint_to_child0: Mat4


class Skeleton:
    def __init__(self, links: Dict[str, object], joints: List[Joint], root: str):
        self.links = links
        self.joints = joints
        self.root = root
        self.children: Dict[str, List[Joint]] = {k: [] for k in links.keys()}
        self.parent_joint: Dict[str, Optional[Joint]] = {k: None for k in links.keys()}
        for j in joints:
            if j.parent in self.children:
                self.children[j.parent].append(j)
            self.parent_joint[j.child] = j

    def topo_order(self) -> List[str]:
        order = []
        stack = [self.root]
        while stack:
            u = stack.pop()
            order.append(u)
            for j in self.children.get(u, []):
                stack.append(j.child)
        return order
