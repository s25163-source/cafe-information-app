import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="카페 위치 정보 앱", layout="wide")

# 세션 상태 초기화 (구역 및 카운트 상태 저장)
if 'selected_cafe' not in st.session_state:
    st.session_state.selected_cafe = None
if 'active_zone' not in st.session_state:
    st.session_state.active_zone = None  # (lat, lon, name)
if 'counter' not in st.session_state:
    st.session_state.counter = 0
if 'user_inside' not in st.session_state:
    st.session_state.user_inside = False

st.title("☕ 카페 정보 & 구역 관리 앱")

# 1. 파일 데이터 로드 (업로드 파일 또는 기본 파일)
uploaded_file = st.sidebar.file_uploader("카페 CSV 데이터 업로드", type=["csv"])

@st.cache_data
def load_data(file):
    if file is not None:
        return pd.read_csv(file)
    else:
        # 데이터 파일이 없을 경우 예시 데이터 생성
        return pd.DataFrame({
            'name': ['카페 A', '카페 B', '카페 C'],
            'lat': [37.5665, 37.5655, 37.5675],
            'lon': [126.9780, 126.9770, 126.9790],
            'address': ['서울 중구 태평로1가', '서울 중구 을지로1가', '서울 중구 무교동']
        })

df = load_data(uploaded_file)

# 필수 컬럼 체크
required_cols = ['name', 'lat', 'lon']
if not all(col in df.columns for col in required_cols):
    st.error(f"CSV 파일에 필수 컬럼({required_cols})이 포함되어 있어야 합니다.")
    st.stop()

# 2. 검색창 구현
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

# 지도 초기 설정 (기본 위치: 서울 시청 또는 선택된 카페)
initial_lat = st.session_state.active_zone['lat'] if st.session_state.active_zone else df['lat'].mean()
initial_lon = st.session_state.active_zone['lon'] if st.session_state.active_zone else df['lon'].mean()
initial_zoom = 18 if st.session_state.active_zone else 15

m = folium.Map(location=[initial_lat, initial_lon], zoom_start=initial_zoom)

# 전체 카페 마커 추가
for idx, row in df.iterrows():
    folium.Marker(
        location=[row['lat'], row['lon']],
        popup=row['name'],
        tooltip=row['name'],
        icon=folium.Icon(color='blue', icon='coffee', prefix='fa')
    ).add_to(m)

# 100m 구역 생성 (활성화된 1개의 카페에만 표시)
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
    
    # 클릭된 위치 근처의 카페 찾기
    matched = df[(abs(df['lat'] - clicked_lat) < 0.0001) & (abs(df['lon'] - clicked_lon) < 0.0001)]
    if not matched.empty:
        cafe_data = matched.iloc[0]
        st.session_state.active_zone = {
            'name': cafe_data['name'],
            'lat': float(cafe_data['lat']),
            'lon': float(cafe_data['lon'])
        }
        st.rerun()

# 3. 사용자 위치 권한 및 구역 안/밖 체크
st.markdown("---")
st.subheader("📍 현재 위치 기반 구역 확인")

# 브라우저 GPS 위치 요청
user_geo = get_geolocation()

if user_geo and st.session_state.active_zone:
    user_lat = user_geo['coords']['latitude']
    user_lon = user_geo['coords']['longitude']
    
    zone_lat = st.session_state.active_zone['lat']
    zone_lon = st.session_state.active_zone['lon']
    
    # 거리를 미터 단위로 계산
    distance = geodesic((user_lat, user_lon), (zone_lat, zone_lon)).meters
    
    st.write(f"현재 선택된 구역: **{st.session_state.active_zone['name']}**")
    st.write(f"구역 중심과의 거리: **{distance:.1f}m**")
    
    # 100m 반경 판단
    is_inside_now = distance <= 100
    
    if is_inside_now and not st.session_state.user_inside:
        st.session_state.counter += 1
        st.session_state.user_inside = True
        st.success("구역에 진입했습니다! (인원 +1)")
    elif not is_inside_now and st.session_state.user_inside:
        st.session_state.counter = max(0, st.session_state.counter - 1)
        st.session_state.user_inside = False
        st.warning("구역에서 이탈했습니다. (인원 -1)")
        
    st.metric(label="현재 구역 내 인원 수", value=f"{st.session_state.counter}명")
else:
    if not st.session_state.active_zone:
        st.info("지도에서 카페를 클릭하거나 검색창에서 선택하여 구역을 설정하세요.")
    else:
        st.info("위치 권한을 허용하시면 구역 진입 여부를 확인합니다.")
