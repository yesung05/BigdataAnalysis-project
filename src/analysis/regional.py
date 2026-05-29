# 지역별 집계 스텁

def summarize_by_region(df, region_col="SIGUNGU_NM"):
    return df.groupby(region_col).size()
