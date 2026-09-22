import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from streamlit_js_eval import get_geolocation
import os

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

# 지도 중심 좌표 및 확대 레벨 유지
if 'map_center' not in st.session_state:
    st.session_state.map_center = [33.38, 126.53]  # 초기값: 제주 중심
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 12                  # 초기값: Zoom 12

st.title("☕ 제주도 카페 위치 정보 & 구역 관리 앱")

# 2. store (1).csv 파일 로드 및 데이터 자동 할당 (캐싱)
@st.cache_data
def load_jeju_store_data():
    file_path = 'store (1).csv'
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df = df.dropna(subset=['상호명', '위도', '경도']).reset_index(drop=True)
        
        # '시군구명'이 없는 경우 기본값 처리
        if '시군구명' not in df.columns:
            df['시군구명'] = '제주시'
            
        # 랜덤 부가 정보 자동 할당
        np.random.seed(42)
        if '좌석수' not in df.columns:
            df['좌석수'] = np.random.randint(10, 101, size=len(df))          # 10 ~ 100개
        if '콘센트수' not in df.columns:
            df['콘센트수'] = np.random.randint(2, 31, size=len(df))          # 2 ~ 30개
        if '1인좌석비율' not in df.columns:
            df['1인좌석비율'] = np.random.randint(10, 61, size=len(df))      # 10 ~ 60%
        if '노트북사용가능' not in df.columns:
            df['노트북사용가능'] = np.random.choice(['O', 'X'], size=len(df), p=[0.7, 0.3])
            
        return df
    else:
        st.error("`store (1).csv` 파일을 찾을 수 없습니다.")
        st.stop()

df = load_jeju_store_data()

# ----------------------------------------------------
# 🎛️ 사이드바: 필터링 섹션
# ----------------------------------------------------
st.sidebar.header("🔍 카페 상세 검색 필터")

# 1. 지역별 필터
region_options = ["전체"] + list(df['시군구명'].dropna().unique())
selected_region = st.sidebar.selectbox("📍 지역 선택 (시/군/구)", region_options)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 시설 및 조건 필터")

# 2. 시설 조건 필터
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

# 조건 필터
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

# 브라우저 위치 데이터 가져오기
user_geo = get_geolocation()

# 3. 카페 검색창 (필터링된 결과 중에서만 선택 가능)
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

# 4. 필터링된 카페 중 가까운 50개 마커 추출 함수
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

# 내 현재 위치 표시 (파란 마커 & 원)
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

# 필터 조건을 만족하는 50개 카페 마커 표시
visible_df = get_nearest_50_filtered_cafes(st.session_state.map_center[0], st.session_state.map_center[1], filtered_df)

for idx, row in visible_df.iterrows():
    popup_text = f"""
    <div style="width:160px">
        <b>{row['상호명']}</b><hr style="margin:5px 0;">
        📍 <b>지역:</b> {row.get('시군구명', '-')}<br>
        🪑 <b>좌석 수:</b> {row['좌석수']}개<br>
        🔌 <b>콘센트 수:</b> {row['콘센트수']}개<br>
        👤 <b>1인 좌석 비율:</b> {row['1인좌석비율']}%<br>
        💻 <b>노트북 사용 가능:</b> {row['노트북사용가능']}
    </div>
    """
    folium.Marker(
        location=[row['위도'], row['경도']],
        popup=folium.Popup(popup_text, max_width=250),
        tooltip=row['상호명'],
        icon=folium.Icon(color='orange', icon='coffee', prefix='fa')
    ).add_to(m)

# 선택 카페 100m 구역 표시
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

# 5. 지도 세션 상태 유지
if map_data:
    if map_data.get("center") is not None:
        st.session_state.map_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom") is not None:
        st.session_state.map_zoom = map_data["zoom"]

# 마커 클릭 시 이벤트
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

# 6. 위치/인원수 재검색 & 카페 부가 정보 상세 보기
st.markdown("---")
col_title, col_btn = st.columns([3, 1])

with col_title:
    st.subheader("📍 현재 위치 기반 구역 및 인원수 확인")

with col_btn:
    if st.button("🔄 위치 및 인원수 재검색", use_container_width=True):
        st.rerun()

if st.session_state.active_zone:
    zone = st.session_state.active_zone
    st.markdown(f"### ☕ **{zone['name']}** 카페 정보")
    
    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
    info_col1.metric("🪑 좌석 수", f"{zone['seats']}개")
    info_col2.metric("🔌 콘센트 수", f"{zone['outlets']}개")
    info_col3.metric("👤 1인 좌석 비율", f"{zone['single_ratio']}%")
    info_col4.metric("💻 노트북 사용", f"{zone['laptop']}")

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
        st.warning("브라우저의 위치 공유 권한을 '허용'하신 후 '🔄 위치 및 인원수 재검색' 버튼을 눌러주세요.")
    elif not st.session_state.active_zone:
        st.info("지도에서 카페 마커를 클릭하거나 검색창에서 선택하여 카페를 지정해 주세요.")
