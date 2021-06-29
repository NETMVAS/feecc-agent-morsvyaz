import typing as tp

Config = tp.Dict[
    tp.Union[int, str], tp.Dict[tp.Union[int, str], tp.Optional[tp.Union[
        str, float, bytes, tp.Dict[
            tp.Union[int, str], tp.Optional[tp.Dict[tp.Union[int, str], tp.Optional[tp.Union[str, float, bytes]]]]]]]]]
