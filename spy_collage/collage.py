import math

import colorgram
import sklearn.cluster
from PIL import Image
from scipy.spatial import distance


def get_features(image_path):
    colors = colorgram.extract(image_path, 2)
    features = []
    for c in colors:
        features.extend(c.rgb)
    return tuple(features)


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
