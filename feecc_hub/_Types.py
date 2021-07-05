import typing as tp

from ._State import State0, State1, State2, State3

Config = tp.Dict[str, tp.Dict[str, tp.Any]]

State = tp.Union[State0, State1, State2, State3]
