import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from streamlit_js_eval import get_geolocation
import os

st.set_page_config(page_title="제주 카페 위치 정보 앱", layout="wide")

# 세션 상태 초기화
if 'selected_cafe' not in st.session_state:
    st.session_state.selected_cafe = None
if 'active_zone' not in st.session_state:
    st.session_state.active_zone = None
if 'counter' not in st.session_state:
    st.session_state.counter = 0
if 'user_inside' not in st.session_state:
    st.session_state.user_inside = False

st.title("☕ 제주도 카페 위치 정보 & 구역 관리 앱")

# 1. store (1).csv 데이터 로드
@st.cache_data
def load_jeju_store_data():
    file_path = 'store (1).csv'
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        # 카페 관련 업종 필터링 (필요시) 및 결측치 제거
        df = df.dropna(subset=['상호명', '위도', '경도'])
        return df
    else:
        st.error("`store (1).csv` 파일을 찾을 수 없습니다. 깃허브 리포지토리에 파일을 올려주세요.")
        st.stop()

df = load_jeju_store_data()

st.sidebar.write(f"📊 등록된 총 카페 수: **{len(df):,}개**")

# 2. 검색창 구현 (상호명으로 검색)
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

# 지도 위치 및 축적 초기 설정
default_lat, default_lon = 33.38, 126.53  # 제주 중심 좌표

initial_lat = st.session_state.active_zone['lat'] if st.session_state.active_zone else default_lat
initial_lon = st.session_state.active_zone['lon'] if st.session_state.active_zone else default_lon
initial_zoom = 18 if st.session_state.active_zone else 11

m = folium.Map(location=[initial_lat, initial_lon], zoom_start=initial_zoom)

# 3. 지도 상 마커 추가 (데이터가 많으므로 효율적인 마커 렌더링)
# 선택된 카페가 없을 때 전역 마커 표시
for idx, row in df.iterrows():
    folium.Marker(
        location=[row['위도'], row['경도']],
        popup=row['상호명'],
        tooltip=row['상호명'],
        icon=folium.Icon(color='orange', icon='coffee', prefix='fa')
    ).add_to(m)

# 선택된 카페 1곳에만 100m 반경 구역 표시
if st.session_state.active_zone:
    zone = st.session_state.active_zone
    folium.Circle(
        location=[zone['lat'], zone['lon']],
        radius=100,  # 100m 구역
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.25,
        popup=f"{zone['name']} (100m 구역)"
    ).add_to(m)

# 지도 렌더링
map_data = st_folium(m, width=800, height=500)

# 지도에서 마커 클릭 시 해당 카페 선택 및 구역 이동
if map_data and map_data.get("last_object_clicked"):
    clicked_lat = map_data["last_object_clicked"]["lat"]
    clicked_lon = map_data["last_object_clicked"]["lng"]
    
    # 클릭된 위치 근처의 카페 찾아 지정
    matched = df[(abs(df['위도'] - clicked_lat) < 0.0001) & (abs(df['경도'] - clicked_lon) < 0.0001)]
    if not matched.empty:
        cafe_data = matched.iloc[0]
        st.session_state.active_zone = {
            'name': cafe_data['상호명'],
            'lat': float(cafe_data['위도']),
            'lon': float(cafe_data['경도'])
        }
        st.rerun()

# 4. 브라우저 위치 권한 수집 및 100m 구역 입출입 카운트
st.markdown("---")
st.subheader("📍 사용자 위치 기반 구역 확인")

user_geo = get_geolocation()

if user_geo and st.session_state.active_zone:
    user_lat = user_geo['coords']['latitude']
    user_lon = user_geo['coords']['longitude']
    
    zone_lat = st.session_state.active_zone['lat']
    zone_lon = st.session_state.active_zone['lon']
    
    # 두 좌표 간 실시간 거리 계산 (미터 단위)
    distance = geodesic((user_lat, user_lon), (zone_lat, zone_lon)).meters
    
    st.write(f"현재 지정된 카페: **{st.session_state.active_zone['name']}**")
    st.write(f"카페 중심과의 거리: **{distance:.1f}m**")
    
    # 100m 판정 및 인원수 카운트
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
