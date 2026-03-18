from dataclasses import dataclass

@dataclass
class Job:
    url: str
    retry_count: int = 0
