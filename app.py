import streamlit as st
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# 1. 페이지 설정
st.set_page_config(page_title="NEIS생기부매뉴얼 (Full Context)", page_icon="📖")
st.title("📖 2025년도 NEIS 생기부 매뉴얼")

# 2. 사이드바 설정
with st.sidebar:
    st.header("설정")
    google_api_key = st.text_input("Google API Key", type="password")
    st.info("💡 책 전체를 AI가 읽고 답변합니다. 답변 속도가 조금 걸릴 수 있습니다.")

if not google_api_key:
    st.warning("👈 왼쪽 사이드바에 API Key를 입력해주세요. 책에 대한 내용이나 당신의 고민을 입력해주세요.")
    st.stop()

# 3. 책 내용 한 번만 로딩하기 (Session State 사용)
if "book_content" not in st.session_state:
    pdf_file = "your_book.pdf"
    
    if os.path.exists(pdf_file):
        with st.spinner("책 전체를 통째로 읽고 있습니다... (최초 1회만 실행)"):
            try:
                loader = PyPDFLoader(pdf_file)
                pages = loader.load()
                # 모든 페이지의 글자를 하나로 합침
                full_text = "\n".join([page.page_content for page in pages])
                st.session_state.book_content = full_text
                st.success(f"책 읽기 완료! (총 {len(pages)} 페이지)")
            except Exception as e:
                st.error(f"책을 읽는 중 오류 발생: {e}")
                st.stop()
    else:
        st.error("폴더에 'your_book.pdf' 파일이 없습니다.")
        st.stop()

# 4. AI 모델 설정 (선생님이 원하시는 2.5 버전 이름으로 설정)
# 만약 2.5가 아직 API에 없다면 'gemini-1.5-pro'가 긴 글 읽기에 최적입니다.
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", # 또는 "gemini-1.5-pro" (긴 글에 더 강력함)
    temperature=0.5,
    google_api_key=google_api_key
)

# 5. 프롬프트 설정 (책 내용 전체를 system prompt에 넣어버림)
system_prompt = (
    "너는 아래 책을 쓴 저자야. 독자의 고민을 듣고 책의 내용을 바탕으로 상담해줘. "
    "책 전체 내용을 다 알고 있으니, 소제목이나 전체적인 맥락도 다 파악해서 답변해. "
    "책에 없는 내용은 지어내지 말고, 책 내용을 인용해서 따뜻하게 말해줘."
    "내용에 알맞은 귀여운 이모티콘도 넣어가면서 답변해줘."
    "표로 정리해서 보여주는 것이 좋을 경우는 깔끔한 표로 작성해서 답해줘."
    "\n\n"
    "--- [책 내용 전체] ---\n"
    f"{st.session_state.book_content}"
)

# 6. 채팅 인터페이스
if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 기록 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 질문 처리
if user_input := st.chat_input("질문해 주세요 (예: 이 책의 목차를 알려줘)"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # 여기서 이전 대화 내역도 함께 보내야 문맥이 유지됨
        messages = [("system", system_prompt)]
        for msg in st.session_state.messages:
            messages.append((msg["role"], msg["content"]))
            
        try:
            with st.spinner("생각 중..."):
                response = llm.invoke(messages)
                message_placeholder.markdown(response.content)
                full_response = response.content
        except Exception as e:
            st.error(f"에러가 발생했습니다: {e}")

    if full_response:
        st.session_state.messages.append({"role": "assistant", "content": full_response})