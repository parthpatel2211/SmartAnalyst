import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import "./ChatInterface.css";

export default function ChatInterface() {
  const [question, setQuestion] = useState("");
  const [chartPreference, setChartPreference] = useState("no");
  const [messages, setMessages] = useState([]);
  const [fullscreenChart, setFullscreenChart] = useState(null);
  const messagesEndRef = useRef(null);


  const askQuestion = async () => {
    const formData = new FormData();
    formData.append("question", question);
    formData.append("chart", chartPreference);

    try {
      const response = await axios.post("http://127.0.0.1:8000/ask", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setMessages([
        ...messages,
        { role: "user", content: question },
        { role: "bot", content: response.data.answer, chart: response.data.chart },
      ]);
      setQuestion("");
    } catch (error) {
      console.error("Error:", error);
      alert("Something went wrong. Please try again.");
    }
  };


  const renderBotContent = (content, chart) => {
    if (Array.isArray(content)) {
      return (
        <table border="1" cellPadding="5" style={{ borderCollapse: "collapse", marginTop: "10px" }}>
          <thead>
            <tr>
              {Object.keys(content[0]).map((header) => (
                <th key={header}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {content.map((row, idx) => (
              <tr key={idx}>
                {Object.values(row).map((val, colIdx) => (
                  <td key={colIdx}>{val}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    } else if (typeof content === "object") {
      return (
        <div style={{ marginTop: "10px" }}>
          {Object.entries(content).map(([key, val]) => (
            <div key={key}>
              <strong>{key}:</strong> {val}
            </div>
          ))}
        </div>
      );
    } else {
      return <div style={{ marginTop: "10px" }}>{content}</div>;
    }
  };

  const handleChartClick = (chartSrc) => {
    setFullscreenChart(chartSrc);
  };

  const closeFullscreenChart = () => {
    setFullscreenChart(null);
  };
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-container">
      <div className="chat-messages">
      {messages.map((msg, idx) => (
    <div
      key={idx}
      className={`message-bubble ${msg.role === "user" ? "user-message" : "bot-message"}`}
    >
      {msg.role === "bot" ? renderBotContent(msg.content, msg.chart) : msg.content}
      {msg.chart && (
        <div className="chart-container">
          <img
            src={msg.chart}
            alt="Chart"
            onClick={() => handleChartClick(msg.chart)}
          />
        </div>
      )}
    </div>
  ))}
  {/* Dummy div at the bottom */}

  <div ref={messagesEndRef} />
</div>

      {fullscreenChart && (
        <div className="fullscreen-chart" onClick={closeFullscreenChart}>
          <span className="close-chart">&times;</span>
          <img src={fullscreenChart} alt="Expanded Chart" />
        </div>
      )}

      <div className="input-container">
  <textarea
    value={question}
    onChange={(e) => setQuestion(e.target.value)}
    placeholder="Type your question..."
    rows={1}
    onKeyDown={(e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        askQuestion();
      }
    }}
  />
        <select
          value={chartPreference}
          onChange={(e) => setChartPreference(e.target.value)}
        >
          <option value="no">No Chart</option>
          <option value="yes">Yes Chart</option>
        </select>
        <button onClick={askQuestion}>Ask</button>
      </div>
    </div>
  );
}

