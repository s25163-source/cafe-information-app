import streamlit as st
import pandas as pd
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

# 지도 뷰 상태 유지 (초기 위치: 제주도 중심, Zoom: 12)
if 'map_center' not in st.session_state:
    st.session_state.map_center = [33.38, 126.53]
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 12

st.title("☕ 제주도 카페 위치 정보 & 구역 관리 앱")

# 2. store (1).csv 데이터 로드
@st.cache_data
def load_jeju_store_data():
    file_path = 'store (1).csv'
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df = df.dropna(subset=['상호명', '위도', '경도'])
        return df
    else:
        st.error("`store (1).csv` 파일을 찾을 수 없습니다. 깃허브 리포지토리에 파일을 올려주세요.")
        st.stop()

df = load_jeju_store_data()

st.sidebar.write(f"📊 등록된 총 카페 수: **{len(df):,}개**")
st.sidebar.info("📌 지도 화면 중앙 기준 가까운 카페 **50개**가 자동 표시됩니다.")

# 3. 검색창 구현
search_term = st.selectbox(
    "카페를 검색하세요:",
    options=["선택하세요"] + list(df['상호명'].unique())
)

if search_term != "선택하세요":
    cafe_data = df[df['상호명'] == search_term].iloc[0]
    st.session_state.selected_cafe = cafe_data
    st.session_state.active_zone = {
        'name': cafe_data['상호명'],
        'lat': float(cafe_data['위도']),
        'lon': float(cafe_data['경도'])
    }
    # 검색 시에만 해당 위치로 이동 및 확대
    st.session_state.map_center = [float(cafe_data['위도']), float(cafe_data['경도'])]
    st.session_state.map_zoom = 16

# 4. 지도 중심점 기준 50개 카페 추출 함수
def get_nearest_50_cafes(center_lat, center_lon, data):
    data_copy = data.copy()
    data_copy['dist'] = (data_copy['위도'] - center_lat)**2 + (data_copy['경도'] - center_lon)**2
    return data_copy.nsmallest(50, 'dist')

# 현재 세션에 저장된 위치와 Zoom 크기로 지도 생성
m = folium.Map(
    location=st.session_state.map_center, 
    zoom_start=st.session_state.map_zoom
)

# 주변 50개 카페 마커 추가
visible_df = get_nearest_50_cafes(st.session_state.map_center[0], st.session_state.map_center[1], df)

for idx, row in visible_df.iterrows():
    folium.Marker(
        location=[row['위도'], row['경도']],
        popup=row['상호명'],
        tooltip=row['상호명'],
        icon=folium.Icon(color='orange', icon='coffee', prefix='fa')
    ).add_to(m)

# 구역 표시
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
map_data = st_folium(m, width=800, height=500, key="jeju_map")

# 지도 조작 시 현재 화면 좌표와 Zoom 레벨을 실시간 저장 (rerun 호출 제거하여 위치 고정)
if map_data:
    if map_data.get("center"):
        st.session_state.map_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom"):
        st.session_state.map_zoom = map_data["zoom"]

# 마커 클릭 이벤트
if map_data and map_data.get("last_object_clicked"):
    clicked_lat = map_data["last_object_clicked"]["lat"]
    clicked_lon = map_data["last_object_clicked"]["lng"]
    
    matched = df[(abs(df['위도'] - clicked_lat) < 0.0001) & (abs(df['경도'] - clicked_lon) < 0.0001)]
    if not matched.empty:
        cafe_data = matched.iloc[0]
        # 활성 구역만 업데이트하고 화면 뷰는 유지
        if st.session_state.active_zone != {'name': cafe_data['상호명'], 'lat': float(cafe_data['위도']), 'lon': float(cafe_data['경도'])}:
            st.session_state.active_zone = {
                'name': cafe_data['상호명'],
                'lat': float(cafe_data['위도']),
                'lon': float(cafe_data['경도'])
            }
            st.rerun()

# 5. 브라우저 위치 기반 구역 확인 및 인원수 카운트
st.markdown("---")
st.subheader("📍 사용자 위치 기반 구역 확인")

user_geo = get_geolocation()

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
    if not st.session_state.active_zone:
        st.info("지도에서 카페 마커를 클릭하거나 상단 검색창에서 선택하여 100m 구역을 생성하세요.")
    else:
        st.info("브라우저 위치 권한 허용 팝업에서 '허용'을 누르면 구역 내 진입 여부를 확인합니다.")
