import refinitiv.dataplatform.eikon as ek
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import requests


# Set your Refinitiv App Key once at import time
REFINITIV_APP_KEY=("cb64a413a4f04804b8a6a82bde9c35087f7f819c")
ek.set_app_key(REFINITIV_APP_KEY)
CACHE_PATH = "attached_assets/analyst_targets.json"

def fetch_monthly_returns(
    tickers: list[str],
    start: str,
    end: str
) -> pd.DataFrame:
    """
    Uses Refinitiv Eikon to fetch monthly adjusted closes for `tickers`
    between `start` and `end` (YYYY-MM-DD), and returns a DataFrame
    of percentage returns (monthly).
    """
    # 1) Call Eikon to get monthly close prices
    #    Field "CLOSE" gives the adjusted close by default
    data = ek.get_timeseries(
        tickers,
        fields=["CLOSE"],
        start_date=start,
        end_date=end,
        interval="monthly"
    )

    # 2) If you get a MultiIndex (ticker, field), pivot it
    if isinstance(data.columns, pd.MultiIndex):
        data = data["CLOSE"]

    # 3) Compute periodic returns
    returns = data.pct_change().dropna(how="all")

    return returns
if __name__ == "__main__":
    # quick test
    df = fetch_monthly_returns(
        ["AAPL.O", "MSFT.O"],
        start="2020-01-01",
        end="2021-12-31"
    )
    print(df.head())
