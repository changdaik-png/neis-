import streamlit as st
import os
import time
import datetime
import google.generativeai as genai
from google.generativeai import caching
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# 1. 페이지 설정
st.set_page_config(page_title="2025생활기록부 매뉴얼", page_icon="📚")

# 2. 사이드바: 설정 및 책 선택
with st.sidebar:
    st.header("설정")
    google_api_key = st.text_input("Google API Key", type="password")
    
    st.divider()
    st.subheader("📚 서버에 저장된 책 목록")
    
    current_dir = os.getcwd()
    pdf_files = [f for f in os.listdir(current_dir) if f.endswith('.pdf')]
    
    if not pdf_files:
        st.error("⚠️ 서버에 PDF 파일이 없습니다!")
        st.info("깃허브 리포지토리에 .pdf 파일을 함께 업로드했는지 확인해주세요.")
        selected_file = None
    else:
        selected_file = st.selectbox("읽을 책을 선택하세요", pdf_files)
        st.success(f"선택됨: {selected_file}")

    st.divider()
    # 대화 초기화 버튼 추가 (오류 발생 시 유용)
    if st.button("🗑️ 대화 기록 지우기"):
        st.session_state.messages = []
        st.rerun()

# 3. 메인 화면
st.title("📖 2025생활기록부 매뉴얼")
st.caption("Google Context Caching + Safety Filter 해제 적용됨")

if not google_api_key:
    st.warning("👈 사이드바에서 Google API Key를 입력해주세요.")
    st.stop()

if not selected_file:
    st.stop()

# API 키 설정
genai.configure(api_key=google_api_key)

# 4. 캐싱 로직
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
            
            # (2) 구글에 파일 업로드
            uploaded_file = genai.upload_file(file_path)
            
            # (3) [중요] 처리 대기 (Processing State 확인)
            # 파일을 업로드하자마자 쓰려고 하면 오류가 나므로 기다립니다.
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2) 
                uploaded_file = genai.get_file(uploaded_file.name)
            
            if uploaded_file.state.name == "FAILED":
                raise ValueError("구글 서버 파일 처리 실패")

            # (4) 캐시 생성
            cache = caching.CachedContent.create(
                model='models/gemini-2.5-flash', # 최신 모델명으로 수정됨
                display_name=selected_file,
                system_instruction=(
                    "너는 2025년 생활기록부 작성지침을 완전하게 알고 있는 전문가야. 질문자의 고민을 듣고 책의 내용을 바탕으로 상담해줘. "
                    "책 전체 내용을 다 알고 있으니, 소제목이나 전체적인 맥락도 다 파악해서 답변해. "
                    "책에 없는 내용은 지어내지 말고, 책 내용을 인용해서 따뜻하게 말해줘."
                    "내용에 알맞은 귀여운 이모티콘도 넣어가면서 답변해줘."
                    "표로 답변을 해야하는 경우는 아래의 규칙을 반드시 지켜서 작성해줘."
                    "[표 작성 규칙] 1.표를 출력할 때는 반드시 표준 Markdown 문법을 준수하세요."
                    "[표 작성 규칙] 2.시각적인 점선(------------)이나 장식용 선을 사용하여 표를 그리지 마세요."
                    "[표 작성 규칙] 3.데이터가 없는 빈 행을 점선으로 채우지 마세요."
                    "[표 작성 규칙] 4. 반드시 | 헤더 | 헤더 | 형식 바로 아래에 |---|---| 형식을 사용하여 표를 렌더링하세요."
                    # [중요] 개인정보 오인 방지 프롬프트
                    "이 문서는 교육부에서 배포한 공개된 '기재요령 가이드라인'이며, 포함된 모든 이름과 정보는 **설명을 위해 만들어진 가상의 예시(Fictional Examples)**입니다. 실제 개인정보가 아니므로 안심하고 분석하여 답변하세요."
                ),
                contents=[uploaded_file],
                ttl=datetime.timedelta(minutes=60)
            )

            # (5) 세션에 정보 저장
            st.session_state.cache_name = cache.name
            st.session_state.current_book = selected_file
            st.session_state.messages = [] 
            st.success(f"✅ 분석 완료! ({selected_file})")
            
        except Exception as e:
            st.error(f"오류 발생: {e}")
            st.stop()

# 5. 모델 로딩
try:
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
        
        # [핵심] 안전 설정: 모든 필터를 꺼버림 (BLOCK_NONE)
        # 생기부 관련 문서(징계, 폭력 등)가 오해받지 않도록 함
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        try:
            # 채팅 기록 구성
            chat_history = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages]
            
            # 답변 요청 (safety_settings 적용)
            response = model.generate_content(
                chat_history,
                safety_settings=safety_settings
            )
            
            # [수정됨] 답변 차단(Safety Block) 확인 로직
            if response.parts:
                full_response = response.text
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "model", "content": full_response})
            else:
                # 답변이 차단되었거나 비어있는 경우 처리
                error_msg = "⚠️ AI가 답변을 생성하지 못했습니다."
                if response.prompt_feedback:
                    error_msg += f"\n(사유: {response.prompt_feedback.block_reason})"
                
                message_placeholder.error(error_msg)
                
                # 에러가 난 경우 마지막 사용자 질문을 삭제하여 다음 대화가 꼬이지 않게 함
                if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                    st.session_state.messages.pop()

        except Exception as e:
            st.error(f"시스템 오류: {e}")
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                st.session_state.messages.pop()
