import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from streamlit_js_eval import get_geolocation
import os
import re
from collections import Counter

st.set_page_config(page_title="제주 카페 위치 정보 앱", layout="wide")

# 1. 세션 상태 초기화
if 'selected_cafe' not in st.session_state:
    st.session_state.selected_cafe = None
if 'active_zone' not in st.session_state:
    st.session_state.active_zone = None
if 'counter' not in st.session_state:
    st.session_state.counter = 0
if 'user_inside' not in st.session_state:
    st.session_state.user_inside = False
if 'reviews' not in st.session_state:
    # 예시 초기 리뷰 데이터
    st.session_state.reviews = {}

# 지도 중심 좌표 및 확대 레벨 유지
if 'map_center' not in st.session_state:
    st.session_state.map_center = [33.38, 126.53]
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 12

st.title("☕ 제주도 카페 위치 정보 & 구역 관리 앱")

# 2. store (1).csv 파일 로드 및 데이터 자동 할당 (캐싱)
@st.cache_data
def load_jeju_store_data():
    file_path = 'store (1).csv'
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df = df.dropna(subset=['상호명', '위도', '경도']).reset_index(drop=True)
        
        if '시군구명' not in df.columns:
            df['시군구명'] = '제주시'
            
        np.random.seed(42)
        if '좌석수' not in df.columns:
            df['좌석수'] = np.random.randint(10, 101, size=len(df))
        if '콘센트수' not in df.columns:
            df['콘센트수'] = np.random.randint(2, 31, size=len(df))
        if '1인좌석비율' not in df.columns:
            df['1인좌석비율'] = np.random.randint(10, 61, size=len(df))
        if '노트북사용가능' not in df.columns:
            df['노트북사용가능'] = np.random.choice(['O', 'X'], size=len(df), p=[0.7, 0.3])
            
        # 대표 키워드 샘플 무작위 할당
        sample_keywords = [
            ["카공하기좋은", "콘센트많음", "조용한"],
            ["뷰가좋은", "디저트맛집", "친절한"],
            ["커피가맛있는", "주차편한", "넓은매장"],
            ["조용한", "1인석많음", "카공하기좋은"],
            ["디저트맛집", "인스타감성", "뷰가좋은"]
        ]
        df['AI_키워드'] = [np.random.choice(sample_keywords) for _ in range(len(df))]
            
        return df
    else:
        st.error("`store (1).csv` 파일을 찾을 수 없습니다.")
        st.stop()

df = load_jeju_store_data()

# 초기 샘플 리뷰 설정
if not st.session_state.reviews:
    for idx, row in df.head(10).iterrows():
        st.session_state.reviews[row['상호명']] = [
            {"rating": 5, "text": "콘센트가 많아서 노트북 작업이나 공부하기 너무 좋고 잔잔한 음악이 흘러나와 조용합니다."},
            {"rating": 4, "text": "커피 향이 아주 깊고 디저트가 맛있네요. 주차장도 넓고 쾌적해요."},
            {"rating": 5, "text": "창밖으로 보이는 뷰가 예술입니다. 카공하기 좋은 테이블도 많아요!"}
        ]

# ----------------------------------------------------
# 🤖 AI 리뷰 요약 및 키워드 추출 함수
# ----------------------------------------------------
def analyze_reviews_ai(review_list):
    if not review_list:
        return "등록된 리뷰가 없습니다.", []
    
    full_text = " ".join([r['text'] for r in review_list])
    
    # 1. 키워드 추출 규칙 기반 매핑
    keyword_map = {
        "카공": "카공하기좋은", "공부": "카공하기좋은", "노트북": "노트북편한",
        "콘센트": "콘센트많음", "조용": "조용한", "분위기": "분위기좋은",
        "뷰": "뷰가좋은", "경치": "뷰가좋은", "바다": "뷰가좋은",
        "맛있": "디저트맛집", "디저트": "디저트맛집", "빵": "디저트맛집",
        "커피": "커피가맛있는", "원두": "커피가맛있는",
        "주차": "주차편한", "넓": "넓은매장", "친절": "친절한"
    }
    
    extracted_keywords = []
    for word, tag in keyword_map.items():
        if word in full_text:
            extracted_keywords.append(tag)
            
    extracted_keywords = list(set(extracted_keywords))
    if not extracted_keywords:
        extracted_keywords = ["추천카페"]
        
    # 2. 요약문 생성
    avg_rating = np.mean([r['rating'] for r in review_list])
    summary = f"⭐ 평균 평점 {avg_rating:.1f}점 / 주요 키워드: {', '.join(['#'+k for k in extracted_keywords])}. 방문객들이 대체로 만족하고 있습니다."
    
    return summary, extracted_keywords

# ----------------------------------------------------
# 🎛️ 사이드바: 필터링 섹션
# ----------------------------------------------------
st.sidebar.header("🔍 카페 상세 검색 필터")

# 1. 지역별 필터
region_options = ["전체"] + list(df['시군구명'].dropna().unique())
selected_region = st.sidebar.selectbox("📍 지역 선택 (시/군/구)", region_options)

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 AI 추천 키워드 필터")

# 2. AI 키워드 다중 선택 필터
all_keywords = ["카공하기좋은", "콘센트많음", "조용한", "뷰가좋은", "디저트맛집", "친절한", "커피가맛있는", "주차편한", "넓은매장", "노트북편한"]
selected_keywords = st.sidebar.multiselect("원하는 특징/분위기 선택 (#키워드)", all_keywords)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 시설 및 조건 필터")

# 3. 시설 조건 필터
min_seats = st.sidebar.slider("🪑 최소 좌석 수", min_value=10, max_value=100, value=10, step=5)
min_outlets = st.sidebar.slider("🔌 최소 콘센트 수", min_value=2, max_value=30, value=2, step=1)
min_single_ratio = st.sidebar.slider("👤 최소 1인 좌석 비율 (%)", min_value=10, max_value=60, value=10, step=5)
laptop_option = st.sidebar.radio("💻 노트북 사용 가능 여부", ["전체", "가능 (O)", "불가 (X)"])

# ----------------------------------------------------
# 🧹 데이터 필터링 적용
# ----------------------------------------------------
filtered_df = df.copy()

# 지역 필터
if selected_region != "전체":
    filtered_df = filtered_df[filtered_df['시군구명'] == selected_region]

# AI 키워드 필터
if selected_keywords:
    filtered_df = filtered_df[
        filtered_df['AI_키워드'].apply(lambda kw_list: any(k in kw_list for k in selected_keywords))
    ]

# 시설 조건 필터
filtered_df = filtered_df[
    (filtered_df['좌석수'] >= min_seats) &
    (filtered_df['콘센트수'] >= min_outlets) &
    (filtered_df['1인좌석비율'] >= min_single_ratio)
]

# 노트북 필터
if laptop_option == "가능 (O)":
    filtered_df = filtered_df[filtered_df['노트북사용가능'] == 'O']
elif laptop_option == "불가 (X)":
    filtered_df = filtered_df[filtered_df['노트북사용가능'] == 'X']

filtered_df = filtered_df.reset_index(drop=True)

st.sidebar.success(f"🎯 조건에 맞는 카페: **{len(filtered_df):,}개** / 전체 {len(df):,}개")

# 위치 정보 연동
user_geo = get_geolocation()

# 3. 카페 검색창
search_options = ["선택하세요"] + list(filtered_df['상호명'].unique()) if len(filtered_df) > 0 else ["조건에 맞는 카페가 없습니다"]
search_term = st.selectbox("카페 선택/검색:", options=search_options)

if search_term not in ["선택하세요", "조건에 맞는 카페가 없습니다"]:
    cafe_data = filtered_df[filtered_df['상호명'] == search_term].iloc[0]
    if st.session_state.selected_cafe is None or st.session_state.selected_cafe['상호명'] != search_term:
        st.session_state.selected_cafe = cafe_data
        st.session_state.active_zone = {
            'name': cafe_data['상호명'],
            'lat': float(cafe_data['위도']),
            'lon': float(cafe_data['경도']),
            'seats': cafe_data['좌석수'],
            'outlets': cafe_data['콘센트수'],
            'single_ratio': cafe_data['1인좌석비율'],
            'laptop': cafe_data['노트북사용가능']
        }
        st.session_state.map_center = [float(cafe_data['위도']), float(cafe_data['경도'])]
        st.session_state.map_zoom = 16

# 4. 가까운 카페 50개 추출
def get_nearest_50_filtered_cafes(center_lat, center_lon, data_frame):
    if len(data_frame) == 0:
        return data_frame
    coords = data_frame[['위도', '경도']].to_numpy(dtype=np.float32)
    target = np.array([center_lat, center_lon], dtype=np.float32)
    dists = np.sum((coords - target) ** 2, axis=1)
    k = min(50, len(data_frame))
    nearest_indices = np.argpartition(dists, k)[:k]
    return data_frame.iloc[nearest_indices]

# 지도 생성
m = folium.Map(
    location=st.session_state.map_center, 
    zoom_start=st.session_state.map_zoom
)

# 사용자 내 위치
if user_geo:
    user_lat = user_geo['coords']['latitude']
    user_lon = user_geo['coords']['longitude']
    
    folium.Marker(
        location=[user_lat, user_lon],
        popup="현재 내 위치",
        tooltip="📍 현재 내 위치",
        icon=folium.Icon(color='blue', icon='user', prefix='fa')
    ).add_to(m)
    
    folium.Circle(
        location=[user_lat, user_lon],
        radius=30,
        color='blue',
        fill=True,
        fill_color='blue',
        fill_opacity=0.3
    ).add_to(m)

# 50개 카페 마커 표시
visible_df = get_nearest_50_filtered_cafes(st.session_state.map_center[0], st.session_state.map_center[1], filtered_df)

for idx, row in visible_df.iterrows():
    kw_tags = " ".join([f"#{k}" for k in row['AI_키워드']])
    popup_text = f"""
    <div style="width:170px">
        <b>{row['상호명']}</b><hr style="margin:5px 0;">
        🏷️ <span style="color:#007BFF; font-size:12px;">{kw_tags}</span><br>
        🪑 <b>좌석 수:</b> {row['좌석수']}개<br>
        🔌 <b>콘센트 수:</b> {row['콘센트수']}개<br>
        💻 <b>노트북:</b> {row['노트북사용가능']}
    </div>
    """
    folium.Marker(
        location=[row['위도'], row['경도']],
        popup=folium.Popup(popup_text, max_width=250),
        tooltip=row['상호명'],
        icon=folium.Icon(color='orange', icon='coffee', prefix='fa')
    ).add_to(m)

# 구역 Circle
if st.session_state.active_zone:
    zone = st.session_state.active_zone
    folium.Circle(
        location=[zone['lat'], zone['lon']],
        radius=100,
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.25,
        popup=f"{zone['name']} (100m 구역)"
    ).add_to(m)

map_data = st_folium(
    m, 
    width=800, 
    height=500, 
    key="jeju_map"
)

# 지도 이동 세션
if map_data:
    if map_data.get("center") is not None:
        st.session_state.map_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom") is not None:
        st.session_state.map_zoom = map_data["zoom"]

# 마커 클릭
if map_data and map_data.get("last_object_clicked"):
    clicked_lat = map_data["last_object_clicked"]["lat"]
    clicked_lon = map_data["last_object_clicked"]["lng"]
    
    if len(filtered_df) > 0:
        coords = filtered_df[['위도', '경도']].to_numpy(dtype=np.float32)
        target_click = np.array([clicked_lat, clicked_lon], dtype=np.float32)
        dists = np.sum((coords - target_click) ** 2, axis=1)
        nearest_idx = np.argmin(dists)
        cafe_data = filtered_df.iloc[nearest_idx]
        
        new_zone = {
            'name': cafe_data['상호명'],
            'lat': float(cafe_data['위도']),
            'lon': float(cafe_data['경도']),
            'seats': cafe_data['좌석수'],
            'outlets': cafe_data['콘센트수'],
            'single_ratio': cafe_data['1인좌석비율'],
            'laptop': cafe_data['노트북사용가능']
        }
        if st.session_state.active_zone != new_zone:
            st.session_state.active_zone = new_zone
            st.rerun()

# 5. 카페 상세 정보 및 AI 리뷰 분석 섹션
st.markdown("---")
col_title, col_btn = st.columns([3, 1])

with col_title:
    st.subheader("📍 현재 위치 기반 구역 및 인원수 확인")

with col_btn:
    if st.button("🔄 위치 및 인원수 재검색", use_container_width=True):
        st.rerun()

if st.session_state.active_zone:
    zone = st.session_state.active_zone
    st.markdown(f"### ☕ **{zone['name']}** 상세 및 AI 리뷰 요약")
    
    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
    info_col1.metric("🪑 좌석 수", f"{zone['seats']}개")
    info_col2.metric("🔌 콘센트 수", f"{zone['outlets']}개")
    info_col3.metric("👤 1인 좌석 비율", f"{zone['single_ratio']}%")
    info_col4.metric("💻 노트북 사용", f"{zone['laptop']}")

    # 📝 리뷰 및 AI 분석 탭
    tab1, tab2 = st.tabs(["🤖 AI 리뷰 요약 & 키워드", "✍️ 리뷰 작성 및 목록"])
    
    cafe_reviews = st.session_state.reviews.get(zone['name'], [])
    
    with tab1:
        ai_summary, ai_keywords = analyze_reviews_ai(cafe_reviews)
        st.info(f"**[AI 요약 리포트]**\n\n{ai_summary}")
        
        st.write("**추출된 핵심 키워드:**")
        kw_html = " ".join([f"<span style='background-color:#e1f5fe; color:#0288d1; padding:4px 8px; border-radius:12px; margin-right:5px;'>#{k}</span>" for k in ai_keywords])
        st.markdown(kw_html, unsafe_allow_html=True)
        
    with tab2:
        # 리뷰 입력 폼
        with st.form(key=f"review_form_{zone['name']}"):
            st.write("**새 리뷰 등록하기**")
            rating = st.slider("평점 선택", 1, 5, 5)
            review_text = st.text_area("리뷰 내용을 작성해 주세요 (예: 콘센트가 많아서 노트북하기 좋아요)")
            submit_btn = st.form_submit_button("리뷰 제출")
            
            if submit_btn and review_text.strip():
                new_entry = {"rating": rating, "text": review_text.strip()}
                if zone['name'] not in st.session_state.reviews:
                    st.session_state.reviews[zone['name']] = []
                st.session_state.reviews[zone['name']].append(new_entry)
                
                # 해당 카페의 AI 키워드 데이터 동적 반영
                _, updated_kws = analyze_reviews_ai(st.session_state.reviews[zone['name']])
                df.loc[df['상호명'] == zone['name'], 'AI_키워드'] = [updated_kws]
                
                st.success("리뷰가 정상 등록되었습니다! AI 분석 결과가 새로고침되었습니다.")
                st.rerun()

        st.markdown("---")
        st.write(f"**전체 리뷰 목록 ({len(cafe_reviews)}개)**")
        for r in reversed(cafe_reviews):
            st.write(f"{'⭐'*r['rating']} | {r['text']}")

# 위치 판단
if user_geo and st.session_state.active_zone:
    user_lat = user_geo['coords']['latitude']
    user_lon = user_geo['coords']['longitude']
    
    zone_lat = st.session_state.active_zone['lat']
    zone_lon = st.session_state.active_zone['lon']
    
    distance = geodesic((user_lat, user_lon), (zone_lat, zone_lon)).meters
    
    st.write(f"현재 내 위치와 카페 중심 거리: **{distance:.1f}m**")
    
    is_inside_now = distance <= 100
    
    if is_inside_now and not st.session_state.user_inside:
        st.session_state.counter += 1
        st.session_state.user_inside = True
        st.success("구역(100m) 내에 진입했습니다! (인원 +1)")
    elif not is_inside_now and st.session_state.user_inside:
        st.session_state.counter = max(0, st.session_state.counter - 1)
        st.session_state.user_inside = False
        st.warning("구역(100m)을 벗어났습니다. (인원 -1)")
        
    st.metric(label="현재 구역 내 인원 수", value=f"{st.session_state.counter}명")
else:
    if not user_geo:
        st.warning("브라우저 위치 권한을 '허용'하신 후 '🔄 위치 및 인원수 재검색' 버튼을 눌러주세요.")
    elif not st.session_state.active_zone:
        st.info("지도에서 카페 마커를 클릭하거나 검색창에서 선택하여 카페를 지정해 주세요.")
