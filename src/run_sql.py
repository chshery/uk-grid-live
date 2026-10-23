import sys, re
import pandas as pd
from sqlalchemy import text
from load_sql import engine

pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 50)

path = sys.argv[1]
sql = open(path).read()
blocks = re.split(r"^-- name: ", sql, flags=re.M)[1:]

with engine.connect() as c:
    for b in blocks:
        name, query = b.split("\n", 1)
        print(f"\n=== {name.strip()} ===")
        print(pd.read_sql(text(query), c).to_string(index=False))