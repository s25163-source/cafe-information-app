import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from streamlit_js_eval import get_geolocation

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

st.title("☕ 제주도 카페 정보 & 구역 관리 앱")

# 1. 제주도 카페 데이터 내장 (CSV 파일 업로드 없이 바로 사용)
@st.cache_data
def load_jeju_cafe_data():
    return pd.DataFrame({
        'name': ['원앤온리', '울트라마린', '울트라바게트', '카페 에프에프', '휴일로'],
        'lat': [33.2393, 33.3225, 33.5165, 33.2458, 33.2372],
        'lon': [126.3688, 126.1963, 126.5218, 126.5612, 126.3768],
        'address': [
            '제주 서귀포시 안덕면 산방로 141',
            '제주 제주시 한경면 일주서로 4611',
            '제주 제주시 관덕로 8',
            '제주 서귀포시 보목포로 86',
            '제주 서귀포시 안덕면 난드르로 49-65'
        ]
    })

df = load_jeju_cafe_data()

# 2. 검색창 구현 (제주도 카페 목록)
search_term = st.selectbox(
    "카페를 검색하세요:",
    options=["선택하세요"] + list(df['name'].unique())
)

if search_term != "선택하세요":
    cafe_data = df[df['name'] == search_term].iloc[0]
    st.session_state.selected_cafe = cafe_data
    st.session_state.active_zone = {
        'name': cafe_data['name'],
        'lat': float(cafe_data['lat']),
        'lon': float(cafe_data['lon'])
    }

# 3. 지도 초기 설정 (제주도 중심 좌표 또는 선택된 카페 위치)
default_lat, default_lon = 33.38, 126.53  # 제주도 중앙 부근

initial_lat = st.session_state.active_zone['lat'] if st.session_state.active_zone else default_lat
initial_lon = st.session_state.active_zone['lon'] if st.session_state.active_zone else default_lon
initial_zoom = 17 if st.session_state.active_zone else 11

m = folium.Map(location=[initial_lat, initial_lon], zoom_start=initial_zoom)

# 제주도 카페 마커 추가
for idx, row in df.iterrows():
    folium.Marker(
        location=[row['lat'], row['lon']],
        popup=row['name'],
        tooltip=row['name'],
        icon=folium.Icon(color='orange', icon='coffee', prefix='fa')
    ).add_to(m)

# 선택된 카페 1곳에만 100m 반경 구역 생성
if st.session_state.active_zone:
    zone = st.session_state.active_zone
    folium.Circle(
        location=[zone['lat'], zone['lon']],
        radius=100,  # 100미터
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.2,
        popup=f"{zone['name']} (100m 구역)"
    ).add_to(m)

# 지도 렌더링 및 클릭 이벤트 처리
map_data = st_folium(m, width=800, height=500)

if map_data and map_data.get("last_object_clicked"):
    clicked_lat = map_data["last_object_clicked"]["lat"]
    clicked_lon = map_data["last_object_clicked"]["lng"]
    
    # 클릭한 마커 주변 카페 찾기
    matched = df[(abs(df['lat'] - clicked_lat) < 0.001) & (abs(df['lon'] - clicked_lon) < 0.001)]
    if not matched.empty:
        cafe_data = matched.iloc[0]
        st.session_state.active_zone = {
            'name': cafe_data['name'],
            'lat': float(cafe_data['lat']),
            'lon': float(cafe_data['lon'])
        }
        st.rerun()

# 4. 사용자 위치 권한 및 구역 안/밖 체크
st.markdown("---")
st.subheader("📍 현재 위치 기반 구역 확인")

user_geo = get_geolocation()

if user_geo and st.session_state.active_zone:
    user_lat = user_geo['coords']['latitude']
    user_lon = user_geo['coords']['longitude']
    
    zone_lat = st.session_state.active_zone['lat']
    zone_lon = st.session_state.active_zone['lon']
    
    # 거리 계산 (미터 단위)
    distance = geodesic((user_lat, user_lon), (zone_lat, zone_lon)).meters
    
    st.write(f"현재 선택된 카페: **{st.session_state.active_zone['name']}**")
    st.write(f"카페 중심과의 거리: **{distance:.1f}m**")
    
    # 100m 판단
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
        st.info("지도에서 카페를 클릭하거나 검색창에서 선택하여 100m 구역을 설정하세요.")
    else:
        st.info("브라우저의 위치 권한을 허용하시면 구역 진입 여부를 판별합니다.")
