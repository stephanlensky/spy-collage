import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import colorgram
import numpy as np
import sklearn.cluster
from PIL import Image
from scipy.spatial import distance
from skimage import color as spaces

from spy_collage.color_problem import ColorMatrix, ColorSpace, KeyLine, KeyPoint, solve_colors


@dataclass
class ImageFeatures:
    features: np.ndarray
    image_path: Path
    __image: Optional[Image.Image]

    @property
    def image(self):
        if self.__image is None:
            self.__image = Image.open(self.image_path)
        return self.__image

    def to_dict(self):
        return {"features": list(self.features), "image_path": str(self.image_path)}

    @staticmethod
    def from_dict(d: dict):
        return ImageFeatures(np.asarray(d["features"]), Path(d["image_path"]), None)


def get_features(image_path) -> ImageFeatures:
    colors: list[colorgram.Color] = colorgram.extract(image_path, 1)
    features = []
    for c in colors:
        rgb = list(c.rgb)
        lab = spaces.rgb2lab(rgb)
        # hsl[0] *= 3
        features.extend(lab)
    return ImageFeatures(np.asarray(features), image_path, None)


def get_clusters(features, n):
    km = sklearn.cluster.KMeans(
        n_clusters=n, init="random", n_init=10, max_iter=300, tol=1e-04, random_state=0
    )
    y_km = km.fit_predict(features)
    clusters = [[] for i in range(n)]
    for i, f in enumerate(features):
        clusters[y_km[i]].append(f)
    return clusters, km.cluster_centers_


def sort_features_by_distance(features: list, p):
    features.sort(key=lambda p2: distance.euclidean(p, p2))


def __features_to_image(features_to_path) -> dict[tuple, Image.Image]:
    features_to_image: dict[tuple, Image.Image] = {}
    for f, p in features_to_path.items():
        features_to_image[f] = Image.open(p)
    return features_to_image


def row_collage(features: list, features_to_path: dict[tuple, str]):
    features_to_image = __features_to_image(features_to_path)
    cover_res = features_to_image[features[0]].width

    collage_size_x = math.ceil(math.sqrt(len(features)))
    collage_size_y = collage_size_x

    collage = Image.new("RGB", (collage_size_x * cover_res, collage_size_y * cover_res), "white")

    for i, f in enumerate(features):
        img = features_to_image[f]
        collage.paste(img, ((i % collage_size_x) * cover_res, (i // collage_size_y) * cover_res))

    collage.show()


def spiral_gen(start):
    yield start
    x, y = start[0], start[1] - 1

    dx = 1
    dy = -1
    while True:
        yield x, y
        if x == start[0] and y < start[1]:
            dy = 1
        elif x == start[0] and y > start[1]:
            dy = -1
        elif y == start[1] and x < start[0]:
            dx = 1
            y -= 1
            continue
        elif y == start[1] and x > start[0]:
            dx = -1

        x += dx
        y += dy


def naive_spiral_collage(
    features: list, clusters: list[list], centroids: list, features_to_path: dict[tuple, str]
):
    clusters = clusters.copy()  # don't modify original list
    features_to_image = __features_to_image(features_to_path)
    cover_res = features_to_image[features[0]].width

    collage_size_x = math.ceil(math.sqrt(len(features)))
    collage_size_y = collage_size_x
    centroids = [
        (math.floor(c[0] * collage_size_x), math.floor(c[1] * collage_size_y)) for c in centroids
    ]

    free_arr = [[True for j in range(collage_size_x)] for i in range(collage_size_y)]

    def free(p):
        px, py = p
        if px < 0 or px >= collage_size_x or py < 0 or py >= collage_size_y:
            return False
        return free_arr[py][px]

    collage = Image.new("RGB", (collage_size_x * cover_res, collage_size_y * cover_res), "white")

    spirals = {c: spiral_gen(c) for c in centroids}
    done = False
    while not done:
        done = True
        for i, cluster in enumerate(clusters):
            if not cluster:
                continue
            done = False

            img = features_to_image[cluster.pop(0)]
            placement = next(spirals[centroids[i]])
            while not free(placement):
                placement = next(spirals[centroids[i]])
            free_arr[placement[1]][placement[0]] = False
            collage.paste(img, (placement[0] * cover_res, placement[1] * cover_res))

    collage.show()


def lap_collage(features: list[ImageFeatures], shape: tuple[int, int]):
    width, height = shape
    color_matrix = ColorMatrix(np.asarray([f.features for f in features]), ColorSpace.CIELAB)

    def mkline(x1, y1, x2, y2, r, g, b):
        return KeyLine(
            int(x1 * width),
            int(y1 * height),
            int(x2 * width),
            int(y2 * height),
            np.array([r, g, b]),
        )

    def mkpoint(x, y, r, g, b):
        return KeyPoint(int(x * width), int(y * height), np.array([r, g, b]))

    # key_points = [
    #     KeyPoint(0, 0, np.array([255, 0, 0])),
    #     KeyPoint(int(1 * width), int(1 * height), np.array([255, 0, 255])),
    #     KeyPoint(int(0.5 * width), int(0.5 * height), np.array([0, 255, 0])),
    # ]
    # key_points = [
    #     KeyLine(
    #         int(0.5 * width),
    #         int(0.25 * height),
    #         int(0.55 * width),
    #         int(0.75 * height),
    #         np.array([255, 0, 255]),
    #     )
    # ]
    # key_points = [KeyPoint(int(0.5 * width), int(0.5 * height), np.array([255, 255, 255]))]
    key_points = [
        mkpoint(0, 0.5, 255, 0, 0),
        mkpoint(0.5, 0.5, 0, 255, 0),
        mkpoint(1, 0.5, 0, 0, 255),
        mkline(0, 0, 1, 0, 255, 255, 255),
        mkline(0, 1, 1, 1, 255, 255, 255),
    ]
    # key_points = [
    #     KeyLine(
    #         int(0 * width),
    #         int(0 * height),
    #         int(0 * width),
    #         int(1 * height),
    #         np.array([255, 0, 0]),
    #     ),
    #     KeyLine(
    #         int(0.5 * width),
    #         int(0 * height),
    #         int(0.5 * width),
    #         int(1 * height),
    #         np.array([0, 255, 0]),
    #     ),
    #     KeyLine(
    #         int(1 * width),
    #         int(0 * height),
    #         int(1 * width),
    #         int(1 * height),
    #         np.array([0, 0, 255]),
    #     ),
    # ]

    _, positions = solve_colors(shape, color_matrix, ColorSpace.CIELAB, key_points)

    cover_res = features[0].image.width
    collage = Image.new("RGB", (width * cover_res, height * cover_res), "white")
    for i in range(height):
        for j in range(width):
            collage.paste(features[positions[j * height + i]].image, (j * cover_res, i * cover_res))

    collage.show()
