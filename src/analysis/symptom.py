# 증상별 집계 스텁

def top_symptoms(df, n=20):
    return df['MAIN_SYM_NM'].value_counts().head(n)
