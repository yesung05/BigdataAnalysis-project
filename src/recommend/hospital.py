# 병원 추천 로직 스텁 (E-Gen API 연동 예정)

def recommend_hospitals(lat, lon, symptom, hospital_df, topk=3):
    # 병상/거리/진료과 기준 복합 스코어링 구현 필요
    return hospital_df.head(topk)
