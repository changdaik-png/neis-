import streamlit as st
import os
import time
import google.generativeai as genai
from google.generativeai import caching
import datetime

# 1. 페이지 설정
st.set_page_config(page_title="AI 저자와의 대화 (Server Ver.)", page_icon="📚")

# 2. 사이드바: 설정 및 책 선택
with st.sidebar:
    st.header("설정")
    # API 키는 보안상 입력받는 게 좋지만, 혼자 쓴다면 st.secrets에 넣어도 됩니다.
    google_api_key = st.text_input("Google API Key", type="password")
    
    st.divider()
    st.subheader("📚 서버에 저장된 책 목록")
    
    # [핵심] 현재 서버(깃허브 리포지토리)에 있는 PDF 파일 자동 스캔
    # Railway 서버의 현재 폴더에서 .pdf로 끝나는 파일을 모두 찾습니다.
    current_dir = os.getcwd()
    pdf_files = [f for f in os.listdir(current_dir) if f.endswith('.pdf')]
    
    if not pdf_files:
        st.error("⚠️ 서버에 PDF 파일이 없습니다!")
        st.info("깃허브 리포지토리에 .pdf 파일을 함께 업로드했는지 확인해주세요.")
        selected_file = None
    else:
        # 파일이 여러 개일 경우 선택 가능
        selected_file = st.selectbox("읽을 책을 선택하세요", pdf_files)
        st.success(f"선택됨: {selected_file}")

# 3. 메인 화면
st.title("📖 AI 저자와의 인생 상담소")
st.caption("Google Context Caching 기술이 적용되었습니다.")

if not google_api_key:
    st.warning("👈 사이드바에서 Google API Key를 입력해주세요.")
    st.stop()

if not selected_file:
    st.stop()

# API 키 설정
genai.configure(api_key=google_api_key)

# 4. 캐싱 로직 (서버에 있는 파일 -> 구글 캐시 서버로 전송)
# 세션 상태 초기화
if "cache_name" not in st.session_state:
    st.session_state.cache_name = None
if "current_book" not in st.session_state:
    st.session_state.current_book = ""

# 책이 변경되었거나 캐시가 없으면 생성 시작
if selected_file != st.session_state.current_book or st.session_state.cache_name is None:
    with st.spinner(f"🚀 '{selected_file}' 내용을 분석하여 구글 서버에 저장 중입니다... (최초 1회)"):
        try:
            # (1) 파일 경로 확인
            file_path = os.path.join(current_dir, selected_file)
            
            # (2) 구글에 파일 업로드 (내 서버 -> 구글 서버)
            uploaded_file = genai.upload_file(file_path)
            
            # (3) 처리 대기
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(1)
                uploaded_file = genai.get_file(uploaded_file.name)
            
            if uploaded_file.state.name == "FAILED":
                raise ValueError("구글 서버 파일 처리 실패")

            # (4) 캐시 생성 (유효기간 60분 설정)
            cache = caching.CachedContent.create(
                model='models/gemini-1.5-flash-001', # 또는 gemini-1.5-pro-001
                display_name=selected_file,
                system_instruction=(
                    "너는 이 책을 쓴 저자야. 독자의 고민을 듣고 책의 내용을 바탕으로 상담해줘. "
                    "책의 구체적인 구절이나 사례를 인용해서 답변하면 더 좋아. "
                    "따뜻하고 통찰력 있는 어조를 유지해줘."
                ),
                contents=[uploaded_file],
                ttl=datetime.timedelta(minutes=60)
            )

            # (5) 세션에 정보 저장
            st.session_state.cache_name = cache.name
            st.session_state.current_book = selected_file
            st.session_state.messages = [] # 책이 바뀌면 대화 초기화
            st.success(f"✅ 분석 완료! 이제 빠르고 저렴하게 대화할 수 있습니다.")
            
        except Exception as e:
            st.error(f"오류 발생: {e}")
            st.stop()

# 5. 모델 로딩 및 채팅
try:
    # 캐시된 ID로 모델 불러오기 (토큰 절약의 핵심)
    cached_content = caching.CachedContent.get(st.session_state.cache_name)
    model = genai.GenerativeModel.from_cached_content(cached_content=cached_content)
    
except Exception as e:
    st.error("⚠️ 세션이 만료되었습니다. (1시간 경과) 새로고침 해주세요.")
    st.session_state.cache_name = None
    st.stop()

# 6. 채팅 인터페이스
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_input := st.chat_input("질문해 주세요..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            # 대화 기록을 포함하여 문맥 유지 (최근 10개만 보내기 등 최적화 가능)
            chat_history = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages]
            
            response = model.generate_content(chat_history)
            full_response = response.text
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "model", "content": full_response})
            
        except Exception as e:
            st.error(f"답변 생성 중 오류: {e}")