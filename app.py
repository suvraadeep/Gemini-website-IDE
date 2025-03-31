import streamlit as st
import google.generativeai as genai
import os
from pathlib import Path
import json
import time
from dotenv import load_dotenv
import re
import urllib.parse


st.set_page_config(layout="wide", page_title="Gemini Web Builder (React CDN)")
load_dotenv()

WORKSPACE_DIR = Path("workspace")
WORKSPACE_DIR.mkdir(exist_ok=True)
CSS_FILENAME = "style.css"


try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        st.error("🔴 Google API Key not found. Please ensure GOOGLE_API_KEY is set in your .env file.")
        st.stop()
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-exp-03-25")
    st.sidebar.caption(f"Using Model: `{model_name}`")
    model = genai.GenerativeModel(model_name)
except Exception as e:
    st.error(f"🔴 Failed to configure Gemini or load model '{model_name}': {e}")
    st.stop()

if "messages" not in st.session_state: st.session_state.messages = []
if "selected_file" not in st.session_state: st.session_state.selected_file = None
if "file_content" not in st.session_state: st.session_state.file_content = ""
if "rendered_html" not in st.session_state: st.session_state.rendered_html = ""

def get_workspace_files():
    try: return sorted([f.name for f in WORKSPACE_DIR.iterdir() if f.is_file()])
    except Exception as e: st.error(f"Error listing workspace files: {e}"); return []

def read_file_content(filename):
    if not filename: return None
    if ".." in filename or filename.startswith(("/", "\\")): return None
    filepath = WORKSPACE_DIR / filename
    try:
        with open(filepath, "r", encoding="utf-8") as f: return f.read()
    except FileNotFoundError: return None
    except Exception as e: st.error(f"Error reading file '{filename}': {e}"); return None

def save_file_content(filename, content):
    if not filename: return False
    if ".." in filename or filename.startswith(("/", "\\")): return False
    filepath = WORKSPACE_DIR / filename
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f: f.write(content); return True
    except Exception as e: st.error(f"Error saving file '{filename}': {e}"); return False

def delete_file(filename):
    if not filename: return False
    if ".." in filename or filename.startswith(("/", "\\")): return False
    filepath = WORKSPACE_DIR / filename
    try:
        os.remove(filepath)
        if st.session_state.selected_file == filename: # Clear state if selected file is deleted
            st.session_state.selected_file = None
            st.session_state.file_content = ""
            st.session_state.rendered_html = ""
            st.session_state.pop(f"rendered_for_{filename}", None)
        return True
    except FileNotFoundError: st.warning(f"File '{filename}' not found for deletion."); return False
    except Exception as e: st.error(f"Error deleting file '{filename}': {e}"); return False


def parse_and_execute_commands(ai_response_text):
    parsed_commands = []
    try:
        response_text_cleaned = ai_response_text.strip()
        if response_text_cleaned.startswith("```json"): response_text_cleaned = response_text_cleaned[7:-3].strip()
        elif response_text_cleaned.startswith("```"): response_text_cleaned = response_text_cleaned[3:-3].strip()
        commands = json.loads(response_text_cleaned) # Strict parsing
        if not isinstance(commands, list): return [{"action": "chat", "content": f"AI (Non-list JSON): {ai_response_text}"}]
        for command in commands:
            if not isinstance(command, dict): parsed_commands.append({"action": "chat", "content": f"Skipped: {command}"}); continue
            action=command.get("action"); filename=command.get("filename"); content=command.get("content")
            parsed_commands.append(command)
            if action=="create_update":
                if filename and content is not None:
                    if not save_file_content(filename, content): st.warning(f"Failed save '{filename}'.")
                else: st.warning(f"⚠️ Invalid 'create_update': {command}")
            elif action=="delete":
                if filename: delete_file(filename)
                else: st.warning(f"⚠️ Invalid 'delete': {command}")
            elif action=="chat": pass
            else: st.warning(f"⚠️ Unknown action '{action}': {command}")
        return parsed_commands
    except json.JSONDecodeError as e:
        st.error(f"🔴 Invalid JSON: {e}\nTxt:\n'{ai_response_text[:500]}...'")
        return [{"action": "chat", "content": f"AI(Invalid JSON): {ai_response_text}"}]
    except Exception as e:
        st.error(f"🔴 Error processing commands: {e}")
        return [{"action": "chat", "content": f"Error processing commands: {e}"}]


def call_gemini(history):
    safe_history = []
    for msg in history:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            safe_history.append({"role": msg["role"], "content": str(msg["content"])})

    instruction = """
    You are an AI assistant that helps users create web pages and simple web applications.
    Your goal is to generate HTML, CSS, JavaScript code, or self-contained React preview files.
    Based on the user's request, you MUST respond ONLY with a valid JSON array containing file operation objects.

    **JSON FORMATTING RULES (VERY IMPORTANT):**
    1.  The entire response MUST be a single JSON array starting with '[' and ending with ']'.
    2.  All keys (like "action", "filename", "content") MUST be enclosed in **double quotes** (").
    3.  All string values (like filenames and the large code content) MUST be enclosed in **double quotes** ("). Single quotes (') or backticks (`) are NOT ALLOWED for keys or string values in the JSON structure.
    4.  Special characters within the "content" string (like newlines, double quotes inside the code) MUST be properly escaped (e.g., use '\\n' for newlines, '\\"' for double quotes).

    **EXAMPLE of Correct JSON action object:**
    {
        "action": "create_update",
        "filename": "example.html",
        "content": "<!DOCTYPE html>\\n<html>\\n<head>\\n  <title>Example</title>\\n</head>\\n<body>\\n  <h1>Hello World!</h1>\\n  <p>This contains a \\"quote\\" example.</p>\\n</body>\\n</html>"
    }

    Possible action objects in the JSON array:
    - {"action": "create_update", "filename": "path/to/file.ext", "content": "file content string here..."}
    - {"action": "delete", "filename": "path/to/file.ext"}
    - {"action": "chat", "content": "Your helpful answer string here..."}

    **VERY IMPORTANT - UPDATING FILES:**
    If the user asks you to modify an existing file (e.g., "add a footer to index.html", "change the button color in style.css"), you MUST provide the **ENTIRE**, complete, updated file content within the 'content' field of the 'create_update' action object, following all JSON formatting rules. Do NOT provide only the changed lines or a diff.

    **REACT PREVIEWS:**
    If the user asks for a simple React component/app to preview, generate a SINGLE self-contained HTML file (e.g., 'react_preview.html') using 'create_update'. This file MUST use CDN links for React/ReactDOM/Babel, have a <div id="root">, include JSX in a <script type="text/babel"> tag, render to the root, and include CSS in <style> tags within the <head>. (Ensure valid JSON).

    **GENERAL:**
    Use standard filenames ('index.html', 'style.css', 'script.js'). The standard CSS file for injection is 'style.css'. If unsure, ask the user. Respond ONLY with the JSON array. Use 'chat' action for questions or explanations.
    """
    current_files = get_workspace_files()
    file_list_prompt = f"Current files in workspace: {', '.join(current_files) if current_files else 'None'}"
    gemini_history = []
    gemini_history.append({"role": "user", "parts": [{"text": f"{instruction}\n{file_list_prompt}"}]})
    gemini_history.append({"role": "model", "parts": [{"text": '[{"action": "chat", "content": "Okay, I understand the strict JSON formatting rules (double quotes, escaping) and the need to provide full file content on updates. I will respond only with the valid JSON array. Ready."}]'}]})
    for msg in safe_history:
        role = "user" if msg["role"] == "user" else "model"; content_text = msg["content"]
        if role == "model" and isinstance(msg["content"], list):
            try: content_text = json.dumps(msg["content"])
            except Exception: content_text = str(msg["content"])
        gemini_history.append({"role": role, "parts": [{"text": content_text}]})
    try:
        response = model.generate_content(gemini_history); return response.text
    except Exception as e:
        if "429" in str(e): st.error("🔴 Gemini API Quota/Rate Limit Exceeded.")
        else: st.error(f"🔴 Gemini API call failed: {e}")
        error_content = f"Error calling AI: {str(e)}".replace('"',"'"); return json.dumps([{"action": "chat", "content": error_content}])


with st.sidebar:
    st.header("💬 Chat with AI")
    st.markdown("Ask the AI to create or modify web files (HTML, CSS, JS, React CDN Previews).")
    st.caption(f"Using Model: `{model_name}`")
    chat_container = st.container(height=500)
    with chat_container:
        if st.session_state.messages:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    if isinstance(message.get("content"), list) and message.get("role") == "assistant":
                        display_text = ""; chat_messages = []
                        for command in message["content"]:
                            if not isinstance(command, dict): continue
                            action = command.get("action"); filename = command.get("filename")
                            if action == "create_update": display_text += f"📝 Create/Update: `{filename}`\n"
                            elif action == "delete": display_text += f"🗑️ Delete: `{filename}`\n"
                            elif action == "chat": chat_messages.append(command.get('content', '...'))
                            else: display_text += f"⚠️ {command.get('content', f'Unknown action: {action}')}\n"
                        final_display = (display_text + "\n".join(chat_messages)).strip()
                        if not final_display: final_display = "(No action)"
                        st.markdown(final_display)
                    else: st.write(str(message.get("content", "")))
        else: st.info("Chat history empty.")
    if prompt := st.chat_input("e.g., Create index.html with a title"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("🧠 AI Thinking..."):
            ai_response_text = call_gemini(st.session_state.messages)
            executed_commands = parse_and_execute_commands(ai_response_text)
            st.session_state.messages.append({"role": "assistant", "content": executed_commands})
            st.rerun()

st.title("🤖 AI Web Builder (React CDN Preview)")
tab1, tab2 = st.tabs([" 📂 Workspace ", " 👀 Preview "])

with tab1:
    st.header("Workspace & Editor")
    st.markdown("---")
    st.subheader("Files")
    available_files = get_workspace_files()
    if not available_files: st.info(f"Workspace '{WORKSPACE_DIR.name}' empty.")
    current_selection_index = 0; options = [None] + available_files
    if st.session_state.selected_file in options:
        try: current_selection_index = options.index(st.session_state.selected_file)
        except ValueError: st.session_state.selected_file = None
    selected_file_option = st.selectbox("Select file:", options=options, format_func=lambda x: "--- Select ---" if x is None else x, key="ws_file_select", index=current_selection_index)
    st.subheader("Edit Code")
    editor_key = f"editor_{st.session_state.selected_file or 'none'}"
    if selected_file_option != st.session_state.selected_file:
        st.session_state.selected_file = selected_file_option
        st.session_state.file_content = read_file_content(st.session_state.selected_file) or "" if st.session_state.selected_file else ""
        st.session_state.rendered_html = ""; st.session_state.pop(f"rendered_for_{st.session_state.selected_file}", None)
        st.rerun()
    if st.session_state.selected_file:
        st.caption(f"Editing: `{st.session_state.selected_file}`")
        file_ext = Path(st.session_state.selected_file).suffix.lower()
        lang_map = {".html": "html", ".css": "css", ".js": "javascript", ".py":"python", ".md": "markdown", ".json": "json", ".jsx":"javascript", ".vue":"vue", ".svelte":"svelte", ".txt":"text"}
        language = lang_map.get(file_ext)
        edited_content = st.text_area("Code Editor", value=st.session_state.file_content, height=400, key=editor_key, label_visibility="collapsed", args=(language,))
        if edited_content != st.session_state.file_content:
             if st.button("💾 Save Manual Changes"):
                if save_file_content(st.session_state.selected_file, edited_content):
                    st.session_state.file_content = edited_content; st.success(f"Saved: `{st.session_state.selected_file}`")
                    st.session_state.rendered_html = ""; st.session_state.pop(f"rendered_for_{st.session_state.selected_file}", None)
                    time.sleep(0.5); st.rerun()
                else: st.error("Failed to save.")
    else:
        st.info("Select a file to edit.")
        st.text_area("Code Editor", value="Select a file...", height=400, key="editor_placeholder", disabled=True, label_visibility="collapsed")

with tab2:
    st.header("Live Preview")
    st.markdown("---")
    css_applied_info = ""

    if st.session_state.selected_file:
        if st.session_state.selected_file.lower().endswith(('.html', '.htm')):
            current_file_content_for_preview = read_file_content(st.session_state.selected_file)
            rendered_marker_key = f"rendered_for_{st.session_state.selected_file}"
            needs_render_update = False
            if current_file_content_for_preview is not None:
                 needs_render_update = (not st.session_state.rendered_html or st.session_state.get(rendered_marker_key) != current_file_content_for_preview)
            else:
                 st.session_state.rendered_html = ""; st.session_state.pop(rendered_marker_key, None)

            if needs_render_update:
                if current_file_content_for_preview is not None:
                    final_html = current_file_content_for_preview
                    is_react_cdn_preview = "<script src=\"https://unpkg.com/@babel/standalone" in final_html
                    css_applied_info = ""
                    if not is_react_cdn_preview:
                        css_content = read_file_content(CSS_FILENAME)
                        if css_content:
                            style_tag = f"\n<style>\n{css_content}\n</style>\n"
                            head_match = re.search(r"</head>", final_html, re.IGNORECASE)
                            if head_match:
                                injection_point = head_match.start()
                                final_html = final_html[:injection_point] + style_tag + final_html[injection_point:]
                                css_applied_info = f"🎨 Injected `{CSS_FILENAME}`."
                    st.session_state.rendered_html = final_html
                    st.session_state[rendered_marker_key] = current_file_content_for_preview

                else:
                    st.warning(f"Could not read `{st.session_state.selected_file}` for preview.")
                    st.session_state.rendered_html = "Error reading file for preview."
                    st.session_state.pop(rendered_marker_key, None)


            if st.session_state.rendered_html and "Error reading file" not in st.session_state.rendered_html:
                st.info(f"Previewing: `{st.session_state.selected_file}`")
                st.markdown("---")

                try:

                    encoded_html = urllib.parse.quote(st.session_state.rendered_html)
                    data_uri = f"data:text/html;charset=utf-8,{encoded_html}"
                    st.markdown(f'<a href="{data_uri}" target="_blank" rel="noopener noreferrer"><button>🚀 Open Preview in New Window</button></a>', unsafe_allow_html=True)
                    st.caption("_(Uses Data URI - best for self-contained HTML/CSS/JS)_")
                except Exception as e:
                    st.warning(f"Could not create 'Open in New Window' link: {e}")


                st.components.v1.html(st.session_state.rendered_html, height=600, scrolling=True)
                st.markdown("---")
                preview_note = "Note: Basic HTML Preview."
                if "<script src=\"https://unpkg.com/@babel/standalone" in st.session_state.rendered_html:
                     preview_note = "Note: Preview uses CDN links & in-browser transpiling for simple React demos."

                if not is_react_cdn_preview and f"Injected `{CSS_FILENAME}`" in css_applied_info:
                     preview_note += f" {css_applied_info}"
                st.caption(preview_note)

            elif "Error reading file" in str(st.session_state.rendered_html):
                 st.error("Preview failed: Could not read the HTML file.")

        else: # File selected, but not HTML
            st.info(f"Preview is available for HTML files only. Selected: `{st.session_state.selected_file}`")
            st.session_state.rendered_html = ""
            st.session_state.pop(f"rendered_for_{st.session_state.selected_file}", None)
    else: # No file selected
        st.info("Select an HTML file from the 'Workspace' tab to see a preview.")
        st.session_state.rendered_html = ""

st.sidebar.markdown("---")
st.sidebar.warning("""
    **Prototype Limitations & Warnings:**
    - **Security:** AI can modify files directly! Use locally & cautiously. **Do not expose publicly.**
    - **File Operations:** Basic create/update/delete. Errors possible.
    - **Preview:** Basic HTML rendering. Attempts `style.css` injection. Can render simple React CDN examples. **No build process, linked JS/CSS (unless injected), etc.** "Open in New Window" uses Data URI and has limitations (URL length, no relative paths for images).
    - **AI Reliability:** AI might misunderstand, generate invalid JSON/code, or fail updates. Prompt tuning helps. Errors are caught, but file ops may fail.
    - **State:** Lost on browser refresh.
""", icon="⚠️")