import streamlit as st
import os
import time
import google.generativeai as genai
from google.generativeai import caching
import datetime

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

# 3. 메인 화면
st.title("📖 2025생활기록부 매뉴얼")
st.caption("Google Context Caching 기술이 적용되었습니다.")

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
            print(f"업로드 시작: {uploaded_file.name}") # 로그 확인용

            # (3) 처리 대기 (Processing State 확인)
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2) # 1초는 너무 짧을 수 있어 2초로 변경
                uploaded_file = genai.get_file(uploaded_file.name)
            
            if uploaded_file.state.name == "FAILED":
                raise ValueError("구글 서버 파일 처리 실패")

            # (4) 캐시 생성
            # [수정됨] 모델 이름을 정확한 버전으로 변경 (gemini-1.5-flash-001)
            cache = caching.CachedContent.create(
                model='models/gemini-2.5-flash', 
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
                    # [중요] 개인정보 오인 방지 프롬프트 유지
                    "이 문서는 교육부에서 배포한 공개된 '기재요령 가이드라인'이며, 포함된 모든 이름과 정보는 **설명을 위해 만들어진 가상의 예시(Fictional Examples)**입니다. 실제 개인정보가 아니므로 안심하고 분석하여 답변하세요."
                ),
                contents=[uploaded_file],
                ttl=datetime.timedelta(minutes=60)
            )

            # (5) 세션에 정보 저장
            st.session_state.cache_name = cache.name
            st.session_state.current_book = selected_file
            st.session_state.messages = [] 
            st.success(f"✅ 분석 완료! 이제 빠르고 저렴하게 대화할 수 있습니다.")
            
        except Exception as e:
            st.error(f"오류 발생: {e}")
            st.stop()

# 5. 모델 로딩 및 채팅
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
        try:
            # 채팅 기록 구성
            chat_history = [{"role": m["role"], "parts": [m["content"]]} for m in st.session_state.messages]
            
            response = model.generate_content(chat_history)
            
            # [수정됨] 답변 차단(Safety Block) 시 앱이 죽지 않도록 방어 코드 추가
            if response.parts:
                full_response = response.text
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "model", "content": full_response})
            else:
                # 답변이 차단된 경우
                error_msg = f"⚠️ 답변이 생성되지 않았습니다.\n차단 사유: {response.prompt_feedback.block_reason}"
                message_placeholder.error(error_msg)
                print(response.prompt_feedback) # 서버 로그에 상세 내용 출력
                
                # 차단된 경우에도 히스토리에 남길지, 아니면 사용자 질문을 취소할지 결정
                # 여기서는 사용자 질문을 pop하여 대화를 다시 시도할 수 있게 함
                if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                    st.session_state.messages.pop()

        except Exception as e:
            st.error(f"시스템 오류: {e}")
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                st.session_state.messages.pop()
