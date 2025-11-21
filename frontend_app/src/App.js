import React, { useState } from "react";
import FileUploader from "./FileUploader";
import ChatInterface from "./ChatInterface";

function App() {
  const [columns, setColumns] = useState([]);

  return (
    <div className="App">
      <h1>Smart Analyst 🤖</h1>
      <FileUploader onUploadSuccess={(cols) => setColumns(cols)} />
      {columns.length > 0 && <ChatInterface />}
    </div>
  );
}

export default App;
