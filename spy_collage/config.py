from typing import Any


class Config:
    __config: dict[str, Any] = {}

    @staticmethod
    def init(ctx):
        Config.__config.update(ctx.params)

    @staticmethod
    def get(key):
        return Config.__config[key]

    @staticmethod
    def set(key, value):
        Config.__config[key] = value
