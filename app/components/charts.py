import plotly.express as px

# 재사용 차트 함수 모음

def line_chart(df, x, y, title="라인차트"):
    return px.line(df, x=x, y=y, title=title)
