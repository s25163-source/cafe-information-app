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

# 사용자가 조작한 지도의 중심 좌표 및 확대 레벨 유지
if 'map_center' not in st.session_state:
    st.session_state.map_center = [33.38, 126.53]  # 초기값: 제주도 중심
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 12                  # 초기값: 확대 12

st.title("☕ 제주도 카페 위치 정보 & 구역 관리 앱")

# 2. store (1).csv 데이터 로드 및 좌표 배열 캐싱
@st.cache_data
def load_jeju_store_data():
    file_path = 'store (1).csv'
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df = df.dropna(subset=['상호명', '위도', '경도']).reset_index(drop=True)
        coords = df[['위도', '경도']].to_numpy(dtype=np.float32)
        return df, coords
    else:
        st.error("`store (1).csv` 파일을 찾을 수 없습니다. 깃허브 리포지토리에 파일을 올려주세요.")
        st.stop()

df, coords_array = load_jeju_store_data()

st.sidebar.write(f"📊 등록된 총 카페 수: **{len(df):,}개**")
st.sidebar.info("📍 내 위치(파란 마커)가 지도 위에 표시됩니다.")

# 브라우저 위치 데이터 가져오기
user_geo = get_geolocation()

# 3. 카페 검색창
search_term = st.selectbox(
    "카페를 검색하세요:",
    options=["선택하세요"] + list(df['상호명'].unique())
)

if search_term != "선택하세요":
    cafe_data = df[df['상호명'] == search_term].iloc[0]
    if st.session_state.selected_cafe is None or st.session_state.selected_cafe['상호명'] != search_term:
        st.session_state.selected_cafe = cafe_data
        st.session_state.active_zone = {
            'name': cafe_data['상호명'],
            'lat': float(cafe_data['위도']),
            'lon': float(cafe_data['경도'])
        }
        st.session_state.map_center = [float(cafe_data['위도']), float(cafe_data['경도'])]
        st.session_state.map_zoom = 16

# 4. 빠른 50개 카페 추출 함수
def get_nearest_50_cafes_fast(center_lat, center_lon):
    target = np.array([center_lat, center_lon], dtype=np.float32)
    dists = np.sum((coords_array - target) ** 2, axis=1)
    k = min(50, len(df))
    nearest_indices = np.argpartition(dists, k)[:k]
    return df.iloc[nearest_indices]

# 지도 생성
m = folium.Map(
    location=st.session_state.map_center, 
    zoom_start=st.session_state.map_zoom
)

# [추가된 기능] 사용자 현재 위치 마커 표시
if user_geo:
    user_lat = user_geo['coords']['latitude']
    user_lon = user_geo['coords']['longitude']
    
    # 내 위치 파란색 마커 추가
    folium.Marker(
        location=[user_lat, user_lon],
        popup="현재 내 위치",
        tooltip="📍 현재 내 위치",
        icon=folium.Icon(color='blue', icon='user', prefix='fa')
    ).add_to(m)
    
    # 내 위치 주변 파란색 반경 원 추가
    folium.Circle(
        location=[user_lat, user_lon],
        radius=30,
        color='blue',
        fill=True,
        fill_color='blue',
        fill_opacity=0.3
    ).add_to(m)

# 주변 50개 카페 마커 표시
visible_df = get_nearest_50_cafes_fast(st.session_state.map_center[0], st.session_state.map_center[1])

for idx, row in visible_df.iterrows():
    folium.Marker(
        location=[row['위도'], row['경도']],
        popup=row['상호명'],
        tooltip=row['상호명'],
        icon=folium.Icon(color='orange', icon='coffee', prefix='fa')
    ).add_to(m)

# 카페 100m 구역 표시 (빨간색)
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

# 지도 렌더링
map_data = st_folium(
    m, 
    width=800, 
    height=500, 
    key="jeju_map"
)

# 5. 지도 위치/확대 상태 유지
if map_data:
    if map_data.get("center") is not None:
        st.session_state.map_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom") is not None:
        st.session_state.map_zoom = map_data["zoom"]

# 마커 클릭 이벤트
if map_data and map_data.get("last_object_clicked"):
    clicked_lat = map_data["last_object_clicked"]["lat"]
    clicked_lon = map_data["last_object_clicked"]["lng"]
    
    target_click = np.array([clicked_lat, clicked_lon], dtype=np.float32)
    dists = np.sum((coords_array - target_click) ** 2, axis=1)
    nearest_idx = np.argmin(dists)
    cafe_data = df.iloc[nearest_idx]
    
    new_zone = {
        'name': cafe_data['상호명'],
        'lat': float(cafe_data['위도']),
        'lon': float(cafe_data['경도'])
    }
    if st.session_state.active_zone != new_zone:
        st.session_state.active_zone = new_zone
        st.rerun()

# 6. 사용자 위치 및 100m 구역 진입 판단
st.markdown("---")
st.subheader("📍 사용자 위치 기반 구역 확인")

if user_geo and st.session_state.active_zone:
    user_lat = user_geo['coords']['latitude']
    user_lon = user_geo['coords']['longitude']
    
    zone_lat = st.session_state.active_zone['lat']
    zone_lon = st.session_state.active_zone['lon']
    
    distance = geodesic((user_lat, user_lon), (zone_lat, zone_lon)).meters
    
    st.write(f"현재 지정된 카페: **{st.session_state.active_zone['name']}**")
    st.write(f"카페 중심과의 거리: **{distance:.1f}m**")
    
    is_inside_now = distance <= 100
    
    if is_inside_now and not st.session_state.user_inside:
        st.session_state.counter += 1
        st.session_state.user_inside = True
        st.success("구역(100m)에 진입했습니다! (인원 +1)")
    elif not is_inside_now and st.session_state.user_inside:
        st.session_state.counter = max(0, st.session_state.counter - 1)
        st.session_state.user_inside = False
        st.warning("구역(100m)에서 이탈했습니다. (인원 -1)")
        
    st.metric(label="현재 구역 내 인원 수", value=f"{st.session_state.counter}명")
else:
    if not user_geo:
        st.warning("브라우저 위치 권한을 '허용'해 주셔야 지도상에 내 위치가 표시됩니다.")
    elif not st.session_state.active_zone:
        st.info("지도에서 카페 마커를 클릭하거나 상단 검색창에서 선택하여 100m 구역을 생성하세요.")
