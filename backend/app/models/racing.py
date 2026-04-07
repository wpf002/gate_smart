import msgspec


class PaperBet(msgspec.Struct):
    bet_id: str
    race_id: str
    horse_id: str
    horse_name: str
    bet_type: str       # win | place | each_way
    odds: str
    stake: float
    status: str = "pending"   # pending | won | lost | void
    returns: float = 0.0
    pnl: float = 0.0
    placed_at: str = ""
    settled_at: str = ""
    race_name: str = ""
    course: str = ""


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
