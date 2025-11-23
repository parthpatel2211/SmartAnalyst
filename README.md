# 🤖 Smart Analyst

An AI-powered data analysis tool that allows you to interact with your CSV data using natural language queries. Built with FastAPI, React, and OpenAI's GPT-4.
<img width="1513" height="522" alt="image" src="https://github.com/user-attachments/assets/1122eb71-537d-42fb-8882-b778049053f2" />


## ✨ Features

- **Natural Language Queries**: Ask questions about your data in plain English
- **Automated Data Analysis**: Leverages GPT-4 to generate pandas code dynamically
- **Visual Insights**: Generate charts and visualizations on demand
- **Data Profiling**: Get instant statistical summaries of your dataset
- **SQL Translation**: Convert natural language to SQL queries (NL2SQL)
- **Interactive Chat Interface**: WhatsApp-style chat UI for seamless interaction
- **Safe Code Execution**: Sandboxed environment for secure code execution

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 14+
- OpenAI API key

### Backend Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/smart-analyst.git
cd smart-analyst
```

2. Install Python dependencies:
```bash
pip install fastapi uvicorn pandas numpy matplotlib openai python-multipart
```

3. Add your OpenAI API key:
   - Open `smart_analyst.py`
   - Replace `"Enter your API key here"` with your actual API key
   - Do the same in `sql_query_api.py`

4. Run the backend server:
```bash
python smart_analyst.py
```

The API will be available at `http://127.0.0.1:8000`

### Frontend Setup

1. Navigate to the frontend directory (or create one):
```bash
mkdir frontend && cd frontend
```

2. Initialize React app (if not already done):
```bash
npx create-react-app .
```

3. Install axios:
```bash
npm install axios
```

4. Copy the React components to the `src` folder:
   - `App.js`
   - `FileUploader.js`
   - `ChatInterface.js`
   - `ChatInterface.css`

5. Start the development server:
```bash
npm start
```

The app will open at `http://localhost:3000`

## 📖 Usage

### Upload Data
1. Click on the file upload button
2. Select a CSV file from your computer
3. Wait for the upload confirmation

### Ask Questions
Once your data is uploaded, you can ask questions like:
- "What is the average sales by region?"
- "Show me the top 10 customers by revenue"
- "How many records are in the dataset?"
- "Create a bar chart of product categories"

### Generate Charts
- Toggle the chart preference to "Yes Chart" when you want visualizations
- Click on chart thumbnails to view them in fullscreen
- Charts are automatically generated based on your query context

## 🏗️ Architecture

```
Smart Analyst
├── Backend (FastAPI)
│   ├── smart_analyst.py      # Main API server
│   ├── profile_api.py         # Data profiling endpoint
│   └── sql_query_api.py       # NL2SQL endpoint
│
└── Frontend (React)
    ├── App.js                 # Main application component
    ├── FileUploader.js        # CSV upload component
    └── ChatInterface.js       # Chat UI component
```

## 🔧 API Endpoints

### POST `/upload`
Upload a CSV file for analysis
- **Body**: `multipart/form-data` with file

### POST `/ask`
Ask questions about the uploaded data
- **Body**: 
  - `question`: Your natural language query
  - `chart`: "yes" or "no" for chart generation

### GET `/profile`
Get statistical profile of the uploaded dataset

### POST `/nl2sql`
Convert natural language to SQL query
- **Body**: 
  - `file`: CSV file
  - `question`: Natural language query

## 🛡️ Security Features

- Sandboxed code execution with restricted builtins
- SQL injection prevention (SELECT-only queries)
- Input validation and error handling
- CORS configuration for frontend access

## 🎨 Customization

### Modify Chat History Limit
In `smart_analyst.py`, adjust the history size:
```python
if len(qa_history) > 5:  # Change 5 to your preferred limit
    qa_history.pop(0)
```

### Change Chart Styling
Modify matplotlib settings in the code generation prompt or post-process charts in the `/ask` endpoint.

### Add New Endpoints
Create new router files and import them in `smart_analyst.py`:
```python
from your_router import router as your_router
app.include_router(your_router)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

