from enum import Enum


class CompressMode(str, Enum):
    auto = "auto"
    on = "on"
    off = "off"