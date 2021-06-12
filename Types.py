import typing as tp

ProductData = tp.Dict[str, tp.Union[str, tp.Dict[str, str], tp.List[str]]]

Config = tp.Dict[str, tp.Dict[str, tp.Any]]

Form = tp.Dict[str, tp.Any]
