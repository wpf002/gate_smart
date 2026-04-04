import msgspec


class Runner(msgspec.Struct):
    horse_id: str
    horse: str
    jockey: str = ""
    trainer: str = ""
    age: str = ""
    weight: str = ""
    form: str = ""
    odds: str = ""
    draw: int = 0


class Race(msgspec.Struct):
    race_id: str
    course: str
    time: str
    title: str = ""
    distance: str = ""
    surface: str = ""
    going: str = ""
    purse: str = ""
    runners: list[Runner] = []
