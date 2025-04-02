# Gemini-website-IDE
![image](https://github.com/user-attachments/assets/9c05c159-75b2-4a46-8b63-a925212de229)


Live link: https://huggingface.co/spaces/suvradeepp/Vibe-Coder-WebD

**Gemini Website IDE** is a lightweight, AI-powered web builder that enables users to create websites through natural language prompts. Built using **Google Gemini 2.5 Pro**, **Streamlit**, and **Python**, the IDE allows users to generate complete HTML, CSS, JavaScript, and React files effortlessly. This project demonstrates the power of large language models in spinning up functional prototypes similar to no-code platforms like Bolt or Lovable.

---

## Features

- **AI-Powered Web Builder**: Generate websites using natural language prompts.
- **Streamlit Interface**: Includes a chat sidebar, live code editor, and real-time preview tab.
- **No Build Process Required**: Live preview directly in the browser without deployment steps.
- **React CDN Support**: Create simple React components with CDN links for easy previews.
- **File Operations**: Create, update, delete files dynamically in a workspace folder.
- **CSS Injection**: Automatically inject CSS into HTML previews for styling.

---

## Project Setup

### Prerequisites
1. Install Python (version 3.7 or higher).
2. Obtain a Google Gemini API key from **Google AI Studio**.

### Installation Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/suvraadeep/Gemini-website-IDE.git
   cd Gemini-website-IDE
   ```

2. Install required Python libraries:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your API key:
   - Create a `.env` file in the project folder.
   - Add the following line to the `.env` file:
     ```plaintext
     GOOGLE_API_KEY="YOUR_API_KEY_HERE"
     ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

---

## Usage Instructions

### Workspace Management
1. Open the app in your browser (default URL: `http://localhost:8501`).
2. Use the **Workspace Tab** to create or edit files (`index.html`, `style.css`, etc.).
3. Save changes manually or let the AI handle file operations.

### Chat with AI
1. Use the chat sidebar to prompt the AI for file creation or modification.
2. Example prompts:
   - "Create an index.html with a title 'Welcome to Gemini IDE'."
   - "Add a footer to index.html."
3. The AI responds with JSON commands that update files in real-time.

### Live Preview
1. Select an HTML file from the workspace tab.
2. View the live preview in the **Preview Tab**.
3. Open previews in a new browser window using the "Open Preview in New Window" button.

---

## File Operations Supported by AI

The AI generates JSON commands for file operations:
- **Create/Update Files**: Provide complete file content for updates.
- **Delete Files**: Remove files from the workspace folder.
- **Chat Responses**: Offer explanations or feedback on user prompts.

---

## Limitations & Warnings

1. **Prototype Only**: Not intended for production use; functionality may be limited.
2. **Security Risks**: Avoid exposing publicly as AI can modify files directly.
3. **File Operations**: Errors may occur during file creation, updates, or deletion.
4. **Preview Constraints**: Supports basic HTML rendering and simple React CDN examples; no build process for linked resources.
5. **AI Reliability**: Generated code may contain errors; prompt tuning is recommended.

---

## Future Improvements

- Add support for advanced frameworks (e.g., Angular, Vue.js).
- Integrate deployment options for production-ready websites.
- Enhance error handling and debugging features.
