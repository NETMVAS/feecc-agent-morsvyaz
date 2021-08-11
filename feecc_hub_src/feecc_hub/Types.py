import typing as tp

import pymongo

Config = tp.Dict[str, tp.Dict[str, tp.Any]]
ConfigSection = tp.Dict[str, tp.Any]
Document = tp.Dict[str, tp.Any]
Collection = pymongo.collection
RequestPayload = tp.Dict[str, tp.Any]
