import math
from abc import ABC, abstractmethod
from colorsys import hsv_to_rgb
from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

import numpy as np
from einops import rearrange
from scipy.optimize import linear_sum_assignment
from skimage import color as spaces


class ColorSpace(Enum):
    RGB = "rgb"
    HSV = "hsv"
    CIELAB = "CIELAB"


@dataclass
class ColorMatrix:
    matrix: np.ndarray
    space: ColorSpace

    def __len__(self) -> int:
        return len(self.matrix)


def convert_space(color: np.ndarray, from_space: ColorSpace, to_space: ColorSpace) -> ColorMatrix:
    if from_space == to_space:
        return ColorMatrix(color, to_space)
    out = None
    if from_space == ColorSpace.CIELAB:
        out = spaces.lab2rgb(
            color
        )  # CIELAB needs special treatment because the CIELAB space is observer-dependent
    else:
        out = spaces.convert_colorspace(color, from_space.value, ColorSpace.RGB.value)

    if to_space == ColorSpace.CIELAB:
        out = spaces.rgb2lab(out)
    else:
        out = spaces.convert_colorspace(out, ColorSpace.RGB.value, to_space.value)
    return ColorMatrix(out, to_space)


class KeyObject(ABC):
    def __init__(self, color: np.ndarray, color_space: ColorSpace) -> None:
        # @todo shape checks
        self.color = {}
        # always store the RGB color data, to calculate values in other spaces from
        self.color[ColorSpace.RGB] = convert_space(color, color_space, ColorSpace.RGB)
        if color_space != ColorSpace.RGB:
            self.color[color_space] = ColorMatrix(color, color_space)

    def getColor(self, output_space: ColorSpace) -> ColorMatrix:
        if output_space in self.color:
            return self.color[output_space]
        else:
            # cache and return the color value in this space
            rgb = self.getColor(ColorSpace.RGB)
            self.color[output_space] = convert_space(rgb.matrix, rgb.space, output_space)
            return self.color[output_space]

    def color_distance_from(
        self, color: np.ndarray, color_space: ColorSpace, distance_space: ColorSpace
    ):
        return np.linalg.norm(
            convert_space(color, color_space, distance_space).matrix
            - self.getColor(distance_space).matrix
        )

    @abstractmethod
    def distanceFrom(self, x: int, y: int) -> Any:
        pass


class KeyPoint(KeyObject):
    def __init__(
        self, x: int, y: int, color: np.ndarray, color_space: ColorSpace = ColorSpace.RGB
    ) -> None:
        super().__init__(color, color_space)
        self.x = x
        self.y = y
        self.__original_color = color
        self.__original_space = color_space

    def distanceFrom(self, x: int, y: int) -> Any:
        return math.dist([x, y], [self.x, self.y])

    def __repr__(self) -> str:
        return f"KeyPoint({self.x}, {self.y}, {self.__original_color}, {self.__original_space})"


class KeyLine(KeyObject):
    def __init__(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: np.ndarray,
        color_space: ColorSpace = ColorSpace.RGB,
    ) -> None:
        super().__init__(color, color_space)
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

    def distanceFrom(self, x: int, y: int) -> Any:
        px = self.x2 - self.x1
        py = self.y2 - self.y1

        norm = px * px + py * py

        u = ((x - self.x1) * px + (y - self.y1) * py) / float(norm)

        if u > 1:
            u = 1
        elif u < 0:
            u = 0

        x3 = self.x1 + u * px
        y3 = self.y1 + u * py

        dx = x3 - x
        dy = y3 - y

        dist = (dx * dx + dy * dy) ** 0.5

        return dist


def mkline(x1, y1, x2, y2, r, g, b, *, width, height):
    return KeyLine(
        int(x1 * width),
        int(y1 * height),
        int(x2 * width),
        int(y2 * height),
        np.array([r, g, b]),
    )


def mkpoint(x, y, r, g, b, *, width, height):
    return KeyPoint(int(x * width), int(y * height), np.array([r, g, b]))


def mkspectrum(x1, y1, x2, y2, h1, h2, n, *, width, height) -> list[KeyPoint]:
    def rgb_norm(c):
        return [int(v * 255) for v in c]

    if n < 2:
        raise ValueError("n must be > 1")
    kp: list[KeyPoint] = [
        mkpoint(x1, y1, *rgb_norm(hsv_to_rgb(h1, 1, 1)), width=width, height=height)
    ]
    x, y, h = x1, y1, h1
    dx = (x2 - x1) / (n - 1)
    dy = (y2 - y1) / (n - 1)
    dh = (h2 - h1) / (n - 1)
    for _ in range(n - 1):
        x, y, h = x + dx, y + dy, h + dh
        kp.append(mkpoint(x, y, *rgb_norm(hsv_to_rgb(h, 1, 1)), width=width, height=height))
    return kp


def create_coordinate_distance_matrix(
    width: int, height: int, key_points: list[KeyObject]
) -> np.ndarray:
    distances = np.empty([width, height, len(key_points)])
    for i in range(width):
        for j in range(height):
            for k in range(len(key_points)):
                distances[i][j][k] = key_points[k].distanceFrom(i, j)
    new_distances = rearrange(distances, "w h k -> (w h) k")
    return new_distances


def create_color_distance_matrix(
    colors: ColorMatrix, distance_space: ColorSpace, key_points: list[KeyObject]
) -> np.ndarray:
    distances = np.empty([len(colors), len(key_points)])
    for i in range(len(colors)):
        for j in range(len(key_points)):
            distances[i][j] = key_points[j].color_distance_from(
                colors.matrix[i], colors.space, distance_space
            )
    return distances


def create_cost_matrix(color_distances: np.ndarray, space_distances: np.ndarray):
    color_distances_squared = color_distances**2
    space_reciprocals = np.reciprocal(np.maximum(space_distances, 1))
    return np.transpose(np.dot(color_distances_squared, np.transpose(space_reciprocals)))


def solve_colors(
    shape: tuple[int, int],
    colors: ColorMatrix,
    distance_space: ColorSpace,
    key_points: Sequence[KeyObject],
):
    key_points = list(key_points)
    if colors.matrix.shape[0] < shape[0] * shape[1]:
        raise ValueError(
            f"Expected colors (shape {colors.matrix.shape} ) to have a first dimension of size"
            f" greater than or equal to the number of positions in the grid ({shape[0]} x"
            f" {shape[1]} = {shape[0] * shape[1]})"
        )
    if len(key_points) < 1:
        raise ValueError("Expected at least one key object to base colors around")
    color_dists = create_color_distance_matrix(colors, distance_space, key_points)
    space_dists = create_coordinate_distance_matrix(shape[0], shape[1], key_points)
    position, color = linear_sum_assignment(create_cost_matrix(color_dists, space_dists))
    return position, color
