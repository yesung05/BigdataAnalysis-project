# 출동 패턴 집계용 스텁

def aggregate_by_station(df):
    """소방서/안전센터별 집계 로직을 구현하세요."""
    return df.groupby("CNTR_NM").size()
