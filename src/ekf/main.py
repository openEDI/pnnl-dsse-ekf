from dataclasses import dataclass


@dataclass
class Config:
    example_param: float = 1.0


def run_step(value: float, config: Config) -> float:
    return value * config.example_param
