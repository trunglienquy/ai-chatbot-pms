
# 🤖 AI Chatbot for Project Management System (PMS)

This is a smart chatbot application that uses **AI to automatically generate SQL queries from natural language**, helping users quickly and accurately retrieve data from the Project Management System (PMS).

---

## 🚀 Technologies Used

| Technology | Description |
|------------|-------------|
| [**Gemini 1.5**](https://ai.google.dev/gemini) | Google's large language model for generating SQL queries from text (supports Vietnamese and English) |
| **Flask** | Lightweight and flexible web framework for Python |
| **MySQL** | Main relational database for storing PMS data |
| **Regex + Validations** | Ensures generated SQL queries are valid and secure |
| **Logging & Error Handling** | Detailed logging and clear error handling |

---

## 🧠 Key Features

- ✅ Accepts natural language questions in **Vietnamese or English**
- ✅ **Gemini** auto-generates `SELECT` queries based on the system schema
- ✅ Performs **SQL safety checks** before execution
- ✅ Returns query results as **JSON** via API
- ✅ Easy to integrate with internal PMS systems

---

## 🗂 Project Structure

```
├── app_chatbot_gemini.py      # Main Flask API
├── config.ini                 # Contains Gemini API Key & DB config (gitignored)
├── gemini_ai.py               # Gemini API interaction logic
├── schema_utils.py            # Load & validate database schema
├── sql_utils.py               # SQL safety and structure checker
├── table_sys.txt              # Simple schema representation (whitelisted tables)
├── process_table/             # (Optional) schema/data processing
├── backup/                    # (Optional) contains backup files and code
└── requirements.txt           # List of required Python packages
```

---

## ⚙️ Setup & Usage

### 1. Create the `config.ini` file:

```ini
[gemini]
api_key = YOUR_GEMINI_API_KEY

[DB]
host = YOUR_HOSTNAME
user = YOUR_USERNAME
password = YOUR_PASSWORD
database = YOUR_DATABASE_NAME
```

### 2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

### 3. Create the `table_sys.txt` file containing the database schema.

### 4. Run the Flask server:

```bash
python app_chatbot_gemini.py
```

### 5. Send a query to the API:

- **Endpoint:** `POST /ask`
- **Headers:** `Content-Type: application/json`
- **Body:**

```json
{
  "question": "List all active projects for client A"
}
```

---

## 🔐 Security Measures

- ❌ **Only allows `SELECT` SQL statements**
- ✅ **Validates table names against a predefined whitelist schema**
- 🔒 Sensitive files like `config.ini`, `app.log`, and the `backup/` folder are safely ignored via `.gitignore`

---

## ✨ Contribution

This is an open-source project intended for learning and research purposes. Contributions, suggestions, and issue reports are welcome!

---

**Made with ❤️ by [trunglienquy](https://github.com/trunglienquy)**
