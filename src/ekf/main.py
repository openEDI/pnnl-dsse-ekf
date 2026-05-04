from dataclasses import dataclass
from pydantic import BaseModel


class ComponentParameters(BaseModel):
    sigma_v: float
    sigma_p: float
    sigma_q: float


@dataclass
class Config:
    example_param: float = 1.0


def run_step(value: float, config: Config) -> float:
    return value * config.example_param


def save_schema() -> None:
    schema = ComponentParameters.schema_json(indent=2)
    with open("schema.json", "w") as f:
        f.write(schema)


if __name__ == "__main__":
    save_schema()
    cfg = Config()
    result = run_step(1.0, cfg)
    print(f"Final result: {result}")
