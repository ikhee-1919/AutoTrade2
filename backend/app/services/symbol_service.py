from app.data.providers.csv_provider import CSVDataProvider


class SymbolService:
    def __init__(self, data_provider: CSVDataProvider) -> None:
        self._data_provider = data_provider

    def list_symbols(self, timeframe: str = "1d") -> list[str]:
        return self._data_provider.list_symbols(timeframe=timeframe)
